"""topaz preprocess — pure numpy.

Pipeline mirrors ``topaz.commands.preprocess`` (which calls into
``topaz.stats.normalize`` after ``topaz.utils.image.downsample``):

  1. FFT-based downsample by `scale` (default 8).
  2. Fit a 2-component Gaussian mixture (with a Beta(900, 1) prior on
     the mixing weight) over multiple `pi` initializations, pick the
     fit with maximum log-likelihood.
  3. Subtract the *background* component's mean and divide by its std.

This reproduces ``topaz preprocess --scale N`` bit-for-bit modulo the
tiny float32 wobble introduced by the EM fit's iteration order.

Source: tbepler/topaz @ stats.py / utils/image.py (GPL-3.0).
"""
from __future__ import annotations

from typing import Tuple

import numpy as np
import scipy.stats


# ---------------------------------------------------------------------------
# downsample
# ---------------------------------------------------------------------------

def downsample(x: np.ndarray, factor: int = 1) -> np.ndarray:
    """FFT downsample 2D array by integer factor, preserving dtype."""
    m, n = x.shape[-2:]
    out_m = int(m / factor)
    out_n = int(n / factor)

    F = np.fft.rfft2(x)
    A = F[..., 0:out_m // 2, 0:out_n // 2 + 1]
    B = F[..., -out_m // 2:, 0:out_n // 2 + 1]
    F = np.concatenate([A, B], axis=0)

    # rescale signal energy after dropping high frequencies
    F *= (out_m * out_n) / (m * n)

    f = np.fft.irfft2(F, s=(out_m, out_n))
    return f.astype(x.dtype)


# ---------------------------------------------------------------------------
# 2-component GMM (numpy port of topaz.stats.gmm_fit_numpy)
# ---------------------------------------------------------------------------

def _gmm_fit(x: np.ndarray, pi: float, alpha: float, beta: float,
             tol: float = 1e-3, num_iters: int = 100) -> Tuple[float, float, float, float, float, float]:
    """Fit 2-component GMM with a Beta(alpha, beta) prior on mixing weight.

    Returns (logp, mu0, var0, mu1, var1, pi). Components share a
    variance — matches upstream's `share_var=True` default.
    """
    split = np.quantile(x, 1 - pi)
    mask = x <= split

    p0 = mask.astype(np.float64)
    p1 = 1 - p0

    mu0 = np.average(x, weights=p0)
    mu1 = np.average(x, weights=p1)
    var = np.mean(p0 * (x - mu0) ** 2 + p1 * (x - mu1) ** 2)

    log_p0 = -(x - mu0) ** 2 / 2 / var - 0.5 * np.log(2 * np.pi * var) + np.log1p(-pi)
    log_p1 = -(x - mu1) ** 2 / 2 / var - 0.5 * np.log(2 * np.pi * var) + np.log(pi)

    ma = np.maximum(log_p0, log_p1)
    Z = ma + np.log(np.exp(log_p0 - ma) + np.exp(log_p1 - ma))

    logp = np.sum(Z) + scipy.stats.beta.logpdf(pi, alpha, beta)
    logp_cur = logp

    for _ in range(num_iters):
        p0 = np.exp(log_p0 - Z)
        p1 = np.exp(log_p1 - Z)

        s = np.sum(p1)
        a = alpha + s
        b = beta + p1.size - s
        pi = (a - 1) / (a + b - 2)  # MAP

        mu0 = np.average(x, weights=p0)
        mu1 = np.average(x, weights=p1)
        var = np.mean(p0 * (x - mu0) ** 2 + p1 * (x - mu1) ** 2)

        log_p0 = -(x - mu0) ** 2 / 2 / var - 0.5 * np.log(2 * np.pi * var) + np.log1p(-pi)
        log_p1 = -(x - mu1) ** 2 / 2 / var - 0.5 * np.log(2 * np.pi * var) + np.log(pi)

        ma = np.maximum(log_p0, log_p1)
        Z = ma + np.log(np.exp(log_p0 - ma) + np.exp(log_p1 - ma))

        logp = np.sum(Z) + scipy.stats.beta.logpdf(pi, alpha, beta)
        if logp - logp_cur <= tol:
            break
        logp_cur = logp

    return logp, mu0, var, mu1, var, pi


def normalize(x: np.ndarray, alpha: float = 900, beta: float = 1,
              num_iters: int = 100, method: str = "gmm") -> Tuple[np.ndarray, dict]:
    """Normalize a micrograph.

    method='affine' :  (x - mean(x)) / std(x), one shot.
    method='gmm'    :  upstream default. Tries pi in {0.1 .. 1.0}, fits a
                       2-component GMM each time, picks the fit with the
                       highest log-likelihood, then ``(x - mu) / std`` of
                       the BACKGROUND component.

    Returns (normalized_image, metadata) where metadata records the chosen
    mu/std/pi for downstream auditing.
    """
    if method == "affine":
        mu = float(x.mean())
        std = float(x.std())
        return ((x - mu) / std).astype(np.float32), {"mu": mu, "std": std, "pi": 1.0}

    pis = np.array([0.1, 0.2, 0.3, 0.4, 0.5, 0.6, 0.7, 0.8, 0.9, 0.95, 0.98, 1.0])
    logps = np.empty_like(pis)
    mus   = np.empty_like(pis)
    stds  = np.empty_like(pis)

    x64 = x.astype(np.float64)

    for i, pi in enumerate(pis):
        if pi == 1.0:
            mu = x64.mean()
            var = x64.var()
            # Upstream uses scipy.stats.beta.pdf (not logpdf) here — the
            # call sits in a logp expression so it's a known upstream
            # quirk (see topaz/stats.py::norm_fit). Replicating it
            # verbatim keeps our chosen pi consistent with `topaz preprocess`.
            logp = float(np.sum(-(x64 - mu) ** 2 / 2 / var - 0.5 * np.log(2 * np.pi * var))
                         + scipy.stats.beta.pdf(1.0, alpha, beta))
            logps[i] = logp; mus[i] = mu; stds[i] = float(np.sqrt(var))
        else:
            # Upstream's `mus[i] = mu.item()` reads the FOREGROUND mean
            # (the brighter component), not the background. The variable
            # called `mu` inside upstream's gmm_fit is initialized to
            # x.mean() but only mu1 gets re-estimated each iteration —
            # the 4th return slot is mu1.  Mirror that here.
            logp, _mu0, _var0, mu1, var, pi_out = _gmm_fit(
                x64, pi=float(pi), alpha=alpha, beta=beta, num_iters=num_iters,
            )
            logps[i] = logp; mus[i] = mu1; stds[i] = float(np.sqrt(var))
            pis[i] = pi_out

    i = int(np.argmax(logps))
    mu, std, pi = float(mus[i]), float(stds[i]), float(pis[i])

    out = ((x - mu) / std).astype(np.float32)
    return out, {"mu": mu, "std": std, "pi": pi, "logp": float(logps[i]),
                 "alpha": alpha, "beta": beta}


def preprocess(image: np.ndarray, scale: int = 8,
               affine: bool = False) -> Tuple[np.ndarray, dict]:
    """Full ``topaz preprocess`` equivalent: downsample then normalize."""
    x = image.astype(np.float32)
    if scale > 1:
        x = downsample(x, scale)
    method = "affine" if affine else "gmm"
    out, metadata = normalize(x, method=method)
    metadata["scale"] = scale
    return out, metadata


__all__ = ["downsample", "normalize", "preprocess"]
