"""FastAPI application for Gemini Web API Wrapper."""

import asyncio
import logging
import os
import tempfile
import time
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI, File, Form, HTTPException, UploadFile, status
from fastapi.responses import JSONResponse, Response

from app.browser_manager import browser_manager
from app.config import settings
from app.models import AskRequest, AskResponse, ErrorResponse, ResponseMeta
from app.gemini_automation import (
    ask_gemini,
    SessionExpiredError,
    QuotaExceededError,
    UnexpectedUIStateError,
    AutomationTimeoutError,
)

# Configure logging
logging.basicConfig(
    level=getattr(logging, settings.log_level.upper()),
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@asynccontextmanager
async def lifespan(app: FastAPI):
    """Lifespan context manager for startup and shutdown."""
    # Startup
    logger.info("Starting Gemini Web API Wrapper...")
    try:
        await browser_manager.start()
        logger.info("Browser manager started successfully")

        # Verify Gemini session
        page = await browser_manager.get_page()
        from app.gemini_automation import ensure_gemini_ready

        try:
            await ensure_gemini_ready(page)
            logger.info("Gemini session verified - ready to accept requests")
        except SessionExpiredError:
            logger.error(
                "Gemini session expired! Please run 'python login_helper.py' or 'node index.js --login' to authenticate."
            )
        except Exception as e:
            logger.warning(f"Could not verify Gemini session: {e}")

    except Exception as e:
        logger.error(f"Failed to start browser manager: {e}")
        raise

    yield

    # Shutdown
    logger.info("Shutting down...")
    await browser_manager.stop()
    logger.info("Shutdown complete")


# Create FastAPI app
app = FastAPI(
    title="Gemini Web API Wrapper",
    description="Local-only API wrapper for Gemini web UI using Playwright automation",
    version="1.1.0",
    lifespan=lifespan,
)


@app.get("/")
async def root():
    """Root endpoint - health check and usage."""
    return {
        "service": "Gemini Web API Wrapper",
        "version": "1.1.0",
        "status": "running" if browser_manager.is_running else "browser_not_ready",
        "usage": {
            "POST /": "Accepts multipart/form-data (prompt and/or image file) and returns binary image",
            "POST /ask": "JSON endpoint for text/multimodal Q&A"
        },
        "docs": "/docs",
    }


@app.get("/health")
async def health_check():
    """Health check endpoint."""
    is_healthy = browser_manager.is_running

    return {
        "healthy": is_healthy,
        "browser_running": browser_manager.is_running,
        "timestamp": time.time(),
    }


@app.post("/")
async def minimal_root_endpoint(
    prompt: Optional[str] = Form(None),
    image: Optional[UploadFile] = File(None)
):
    """
    Minimal universal endpoint:
    Accepts prompt and/or image file, returns binary image or JSON text.
    """
    if not prompt and not image:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Provide at least 'prompt' or an uploaded 'image' file."
        )

    temp_path = None
    files = None

    if image:
        suffix = os.path.splitext(image.filename)[1] if image.filename else ".png"
        with tempfile.NamedTemporaryFile(delete=False, suffix=suffix) as tmp:
            tmp.write(await image.read())
            temp_path = tmp.name
        files = [temp_path]

    await browser_manager.acquire_lock()
    try:
        page = await browser_manager.get_page()
        response_text, model_used, fallback, image_bytes = await ask_gemini(
            page=page,
            prompt=prompt or "",
            model=settings.default_model,
            fallback_to_flash=settings.fallback_to_flash,
            files=files
        )

        if image_bytes:
            return Response(content=image_bytes, media_type="image/png")
        else:
            return JSONResponse(content={"success": True, "text": response_text})

    finally:
        browser_manager.release_lock()
        if temp_path and os.path.exists(temp_path):
            try:
                os.remove(temp_path)
            except Exception:
                pass


@app.post(
    "/ask",
    response_model=AskResponse,
    responses={
        200: {"model": AskResponse},
        400: {"model": ErrorResponse},
        401: {"model": ErrorResponse},
        500: {"model": ErrorResponse},
        503: {"model": ErrorResponse},
    },
)
async def ask_endpoint(request: AskRequest):
    """
    Send a prompt or multimodal input to Gemini.
    """
    start_time = time.time()

    valid_models = ["gemini-2.5-pro", "gemini-2.5-flash"]
    if request.model not in valid_models:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail=f"Invalid model. Must be one of: {valid_models}",
        )

    if not browser_manager.is_running:
        logger.error("Browser not running - attempting to restart")
        try:
            await browser_manager.start()
        except Exception as e:
            raise HTTPException(
                status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
                detail=f"Browser service unavailable: {str(e)}",
            )

    await browser_manager.acquire_lock()

    try:
        page = await browser_manager.get_page()

        response_text, model_used, fallback_triggered, image_bytes = await ask_gemini(
            page=page,
            prompt=request.prompt,
            model=request.model,
            fallback_to_flash=request.fallback_to_flash,
            files=request.files,
        )

        latency_ms = int((time.time() - start_time) * 1000)

        return AskResponse(
            model_requested=request.model,
            model_used=model_used,
            fallback_triggered=fallback_triggered,
            response_text=response_text,
            raw_response_html=None,
            meta=ResponseMeta(latency_ms=latency_ms),
        )

    except SessionExpiredError as e:
        logger.error(f"Session expired: {e}")
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail={"error": "gemini_session_expired", "details": str(e)},
        )

    except QuotaExceededError as e:
        logger.error(f"Quota exceeded: {e}")
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail={"error": "pro_quota_exceeded", "details": str(e)},
        )

    except UnexpectedUIStateError as e:
        logger.error(f"Unexpected UI state: {e}")
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail={"error": "unexpected_ui_state", "details": str(e)},
        )

    except AutomationTimeoutError as e:
        logger.error(f"Automation timeout: {e}")
        raise HTTPException(
            status_code=status.HTTP_504_GATEWAY_TIMEOUT,
            detail={"error": "automation_timeout", "details": str(e)},
        )

    except Exception as e:
        logger.exception(f"Unexpected error: {e}")
        try:
            await browser_manager.restart()
        except Exception:
            pass

        raise HTTPException(
            status_code=status.HTTP_500_INTERNAL_SERVER_ERROR,
            detail={"error": "internal_error", "details": str(e)},
        )

    finally:
        browser_manager.release_lock()


if __name__ == "__main__":
    import uvicorn

    uvicorn.run(
        "app.main:app",
        host=settings.host,
        port=settings.port,
        log_level=settings.log_level.lower(),
    )
