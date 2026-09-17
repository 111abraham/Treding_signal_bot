import os
import sys
import logging
import threading
import time
from typing import Dict, Any, Optional, List, Tuple
import warnings
import numpy as np
import pandas as pd

# Suppress CUDA architecture compatibility advisory warnings
warnings.filterwarnings("ignore", category=UserWarning, module="torch.cuda")

logger = logging.getLogger(__name__)

# Try importing torch safely
DEVICE = "cpu"
try:
    import torch
    if torch.cuda.is_available():
        try:
            _ = torch.zeros(1, device="cuda:0")
            DEVICE = "cuda:0"
        except Exception:
            DEVICE = "cpu"
except ImportError:
    DEVICE = "cpu"


class TimesFMArbiter:
    """
    Google TimesFM 2.5 Foundation Model Candidate Arbiter.
    Evaluates high-conviction candidate trade setups using Google's 200M zero-shot
    time series transformer.
    
    Acts as an institutional secondary consensus check:
    - High Confluence (Agreement) -> Boosts conviction (+10% to +15%) & adds Dual-AI badge.
    - Divergence (Conflict) -> Decreases conviction (-15%) and optionally suppresses signal.
    - Neutral / Sideways -> Retains baseline metrics without confluence boost.
    """

    def __init__(self, repo_id: str = "google/timesfm-2.5-200m-pytorch"):
        self.repo_id = repo_id
        self.device = DEVICE
        self.model = None
        self.status = "uninitialized"  # "uninitialized", "loading", "ready", "error", "disabled"
        self.error_message = None
        self._lock = threading.Lock()
        self._load_thread: Optional[threading.Thread] = None

    def start_background_load(self):
        """Asynchronously loads the TimesFM model in a background daemon thread."""
        with self._lock:
            if self.status in ["loading", "ready"]:
                return
            self.status = "loading"
            self._load_thread = threading.Thread(target=self._load_model_worker, daemon=True)
            self._load_thread.start()

    def _load_model_worker(self):
        """Worker thread to download and initialize TimesFM 2.5."""
        logger.info(f"Initiating TimesFM Foundation Model loading ({self.repo_id})...")
        t0 = time.time()
        try:
            import timesfm
            # Load weights (Windows safe: torch_compile=False)
            model = timesfm.TimesFM_2p5_200M_torch.from_pretrained(
                self.repo_id,
                torch_compile=False
            )
            # Compile with horizon 5, max context 512
            forecast_config = timesfm.ForecastConfig(
                max_context=512,
                max_horizon=128,
                per_core_batch_size=1
            )
            model.compile(forecast_config)
            
            with self._lock:
                self.model = model
                self.status = "ready"
                self.error_message = None
            
            elapsed = time.time() - t0
            logger.info(f"TimesFM 2.5 Candidate Arbiter ready in {elapsed:.1f}s on {self.device}.")
        except Exception as e:
            with self._lock:
                self.status = "error"
                self.error_message = str(e)
            logger.warning(f"Failed to load TimesFM Foundation Model: {e}. Arbiter will operate in pass-through mode.")

    def get_status(self) -> Dict[str, Any]:
        """Returns current runtime state of the TimesFM Arbiter."""
        return {
            "status": self.status,
            "device": self.device,
            "repo_id": self.repo_id,
            "is_ready": self.status == "ready",
            "error": self.error_message
        }

    def evaluate_candidate(
        self,
        closes: np.ndarray,
        signal: Dict[str, Any],
        config: Optional[Dict[str, Any]] = None
    ) -> Dict[str, Any]:
        """
        Cross-validates an actionable candidate setup against TimesFM 2.5 forecast.
        Modifies signal in-place and returns updated signal dictionary.
        """
        cfg = config or {}
        if not cfg.get("enabled", True):
            signal["timesfm_status"] = "disabled"
            signal["dual_ai_confluence"] = False
            return signal

        # Trigger background loading if not yet ready
        if self.status == "uninitialized":
            self.start_background_load()

        if self.status != "ready" or self.model is None:
            # Model still downloading/loading or error - pass through safely
            signal["timesfm_status"] = self.status
            signal["dual_ai_confluence"] = False
            signal["timesfm_consensus"] = "PENDING"
            return signal

        try:
            # Prepare inputs: take up to 512 historical close prices
            context_series = closes[-512:].astype(np.float32)
            if len(context_series) < 30:
                signal["timesfm_status"] = "insufficient_data"
                signal["dual_ai_confluence"] = False
                return signal

            curr_price = float(context_series[-1])

            # Run 5-step zero-shot inference
            point_forecast, _ = self.model.forecast(horizon=5, inputs=[context_series])
            pred_5_steps = point_forecast[0]  # shape: (5,)
            final_pred_price = float(pred_5_steps[-1])

            tfm_return_pct = round(((final_pred_price - curr_price) / curr_price) * 100, 3)

            # Determine TimesFM directional forecast
            if tfm_return_pct > 0.15:
                tfm_direction = "BULLISH"
            elif tfm_return_pct < -0.15:
                tfm_direction = "BEARISH"
            else:
                tfm_direction = "NEUTRAL"

            primary_direction = signal.get("direction", "NEUTRAL")
            current_conviction = float(signal.get("conviction", 50.0))
            conviction_boost = float(cfg.get("conviction_boost", 12.0))
            suppress_on_conflict = bool(cfg.get("suppress_on_conflict", False))

            if tfm_direction == primary_direction:
                # 1. CONSENSUS AGREEMENT: Dual AI Confluence
                consensus = "AGREEMENT"
                dual_confluence = True
                new_conviction = min(99.0, current_conviction + conviction_boost)
                reason = f"Dual AI Confluence: Primary ({primary_direction}) & TimesFM ({tfm_return_pct:+0.2f}%) agree"
            elif tfm_direction == "NEUTRAL":
                # 2. NEUTRAL: TimesFM sees flat consolidation
                consensus = "NEUTRAL"
                dual_confluence = False
                new_conviction = current_conviction
                reason = f"TimesFM Neutral ({tfm_return_pct:+0.2f}%): Sideways drift forecast"
            else:
                # 3. CONFLICT: TimesFM opposes primary setup
                consensus = "CONFLICT"
                dual_confluence = False
                new_conviction = max(15.0, current_conviction - 15.0)
                reason = f"AI Divergence: Primary ({primary_direction}) vs TimesFM ({tfm_direction}, {tfm_return_pct:+0.2f}%)"
                if suppress_on_conflict:
                    signal["is_actionable"] = False

            # Update signal payload
            signal["conviction"] = round(new_conviction, 1)
            signal["dual_ai_confluence"] = dual_confluence
            signal["timesfm_consensus"] = consensus
            signal["timesfm_direction"] = tfm_direction
            signal["timesfm_return_pct"] = tfm_return_pct
            signal["timesfm_target_5"] = round(final_pred_price, 4)
            signal["timesfm_status"] = "ready"
            signal["timesfm_reason"] = reason
            signal["timesfm_forecast"] = [round(float(x), 4) for x in pred_5_steps]

            return signal

        except Exception as ex:
            logger.error(f"Error during TimesFM candidate evaluation: {ex}")
            signal["timesfm_status"] = "error"
            signal["dual_ai_confluence"] = False
            return signal


# Global singleton instance
timesfm_arbiter = TimesFMArbiter()
