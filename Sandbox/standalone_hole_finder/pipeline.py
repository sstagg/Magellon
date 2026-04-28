from __future__ import annotations

import numpy as np

import blob_detector
import correlator
import edge_detector
import hole_stats
import ice_filter
import lattice_fitter
import sampler
import target_convolver
import template_builder
import thresholding

find_blobs = blob_detector.find_blobs
correlate_template = correlator.correlate_template
find_edges = edge_detector.find_edges
calc_hole_stats = hole_stats.calc_hole_stats
calc_ice_and_filter = ice_filter.calc_ice_and_filter
fit_hole_lattice = lattice_fitter.fit_hole_lattice
sample_holes = sampler.sample_holes
make_convolved_targets = target_convolver.make_convolved_targets
create_template = template_builder.create_template
MEAN_STD_METHOD = thresholding.MEAN_STD_METHOD
threshold_correlation = thresholding.threshold_correlation


def _finalize_targets(
    image: np.ndarray,
    holes,
    stats_radius: int,
    ice_i0: float | None,
    ice_tmin: float,
    ice_tmax: float,
    ice_tstdmin: float,
    ice_tstdmax: float,
    conv_vect,
    sample_classes: int,
    sample_count: int,
    sample_category: str,
):
    holes = calc_hole_stats(image, holes, radius=stats_radius)
    good_holes = holes
    if ice_i0 is not None:
        holes, good_holes = calc_ice_and_filter(
            holes,
            i0=ice_i0,
            tmin=ice_tmin,
            tmax=ice_tmax,
            tstdmin=ice_tstdmin,
            tstdmax=ice_tstdmax,
        )

    convolved_holes = make_convolved_targets(good_holes, conv_vect, image.shape)
    if convolved_holes:
        convolved_holes = calc_hole_stats(image, convolved_holes, radius=stats_radius)
        if ice_i0 is not None:
            _, convolved_holes = calc_ice_and_filter(
                convolved_holes,
                i0=ice_i0,
                tmin=ice_tmin,
                tmax=ice_tmax,
                tstdmin=ice_tstdmin,
                tstdmax=ice_tstdmax,
            )

    sampled_holes = sample_holes(
        convolved_holes if convolved_holes else good_holes,
        classes=sample_classes,
        samples=sample_count,
        category=sample_category,
    )
    return holes, good_holes, convolved_holes, sampled_holes


def run_template_hole_finder(
    image: np.ndarray,
    template_filename: str,
    template_diameter: float,
    file_diameter: float = 168.0,
    invert: bool = False,
    multiple: int = 1,
    spacing: float = 100.0,
    angle: float = 0.0,
    correlation_type: str = "cross",
    correlation_filter_sigma: float | None = 1.0,
    cor_image_min: float | None = 0.0,
    threshold_value: float = 3.0,
    threshold_method: str = MEAN_STD_METHOD,
    border: int = 20,
    max_blobs: int = 100,
    max_blob_size: int = 50,
    min_blob_size: int = 0,
    min_blob_roundness: float = 0.8,
    lattice_spacing: float = 100.0,
    lattice_tolerance: float = 0.1,
    lattice_extend: str = "off",
    stats_radius: int = 20,
    ice_i0: float | None = None,
    ice_tmin: float = 0.0,
    ice_tmax: float = 0.1,
    ice_tstdmin: float = 0.05,
    ice_tstdmax: float = 0.5,
    conv_vect: list[tuple[float, float]] | None = None,
    sample_classes: int = 1,
    sample_count: int = -1,
    sample_category: str = "hole_number",
) -> dict[str, object]:
    template = create_template(
        image_shape=image.shape,
        template_filename=template_filename,
        template_diameter=template_diameter,
        file_diameter=file_diameter,
        invert=invert,
        multiple=multiple,
        spacing=spacing,
        angle=angle,
    )
    correlation = correlate_template(
        source_image=image,
        template=template,
        correlation_type=correlation_type,
        correlation_filter_sigma=correlation_filter_sigma,
        cor_image_min=cor_image_min,
    )
    threshold_mask = threshold_correlation(correlation, threshold_value, threshold_method)
    blobs = find_blobs(
        correlation,
        threshold_mask,
        border=border,
        max_blobs=max_blobs,
        max_blob_size=max_blob_size,
        min_blob_size=min_blob_size,
        min_blob_roundness=min_blob_roundness,
    )
    fit = fit_hole_lattice(
        blobs,
        image_shape=image.shape,
        spacing=lattice_spacing,
        tolerance=lattice_tolerance,
        extend=lattice_extend,
    )
    holes, good_holes, convolved_holes, sampled_holes = _finalize_targets(
        image=image,
        holes=fit.holes,
        stats_radius=stats_radius,
        ice_i0=ice_i0,
        ice_tmin=ice_tmin,
        ice_tmax=ice_tmax,
        ice_tstdmin=ice_tstdmin,
        ice_tstdmax=ice_tstdmax,
        conv_vect=conv_vect,
        sample_classes=sample_classes,
        sample_count=sample_count,
        sample_category=sample_category,
    )
    return {
        "source_image": image,
        "edges": None,
        "template": template,
        "correlation": correlation,
        "threshold_mask": threshold_mask,
        "blobs": blobs,
        "lattice": fit.lattice,
        "holes": holes,
        "good_holes": good_holes,
        "convolved_holes": convolved_holes,
        "sampled_holes": sampled_holes,
    }


def run_edge_hole_finder(
    image: np.ndarray,
    template_filename: str,
    template_diameter: float,
    file_diameter: float = 168.0,
    invert: bool = False,
    multiple: int = 1,
    spacing: float = 100.0,
    angle: float = 0.0,
    edge_lpsig: float = 1.0,
    edge_thresh: float | None = 100.0,
    correlation_type: str = "cross",
    correlation_filter_sigma: float | None = 1.0,
    cor_image_min: float | None = 0.0,
    threshold_value: float = 3.0,
    threshold_method: str = MEAN_STD_METHOD,
    border: int = 20,
    max_blobs: int = 100,
    max_blob_size: int = 50,
    min_blob_size: int = 0,
    min_blob_roundness: float = 0.8,
    lattice_spacing: float = 100.0,
    lattice_tolerance: float = 0.1,
    lattice_extend: str = "off",
    stats_radius: int = 20,
    ice_i0: float | None = None,
    ice_tmin: float = 0.0,
    ice_tmax: float = 0.1,
    ice_tstdmin: float = 0.05,
    ice_tstdmax: float = 0.5,
    conv_vect: list[tuple[float, float]] | None = None,
    sample_classes: int = 1,
    sample_count: int = -1,
    sample_category: str = "hole_number",
) -> dict[str, object]:
    edges = find_edges(image, lpsig=edge_lpsig, thresh=edge_thresh)
    template = create_template(
        image_shape=image.shape,
        template_filename=template_filename,
        template_diameter=template_diameter,
        file_diameter=file_diameter,
        invert=invert,
        multiple=multiple,
        spacing=spacing,
        angle=angle,
    )
    correlation = correlate_template(
        source_image=edges,
        template=template,
        correlation_type=correlation_type,
        correlation_filter_sigma=correlation_filter_sigma,
        cor_image_min=cor_image_min,
    )
    threshold_mask = threshold_correlation(correlation, threshold_value, threshold_method)
    blobs = find_blobs(
        correlation,
        threshold_mask,
        border=border,
        max_blobs=max_blobs,
        max_blob_size=max_blob_size,
        min_blob_size=min_blob_size,
        min_blob_roundness=min_blob_roundness,
    )
    fit = fit_hole_lattice(
        blobs,
        image_shape=image.shape,
        spacing=lattice_spacing,
        tolerance=lattice_tolerance,
        extend=lattice_extend,
    )
    holes, good_holes, convolved_holes, sampled_holes = _finalize_targets(
        image=image,
        holes=fit.holes,
        stats_radius=stats_radius,
        ice_i0=ice_i0,
        ice_tmin=ice_tmin,
        ice_tmax=ice_tmax,
        ice_tstdmin=ice_tstdmin,
        ice_tstdmax=ice_tstdmax,
        conv_vect=conv_vect,
        sample_classes=sample_classes,
        sample_count=sample_count,
        sample_category=sample_category,
    )
    return {
        "source_image": image,
        "edges": edges,
        "template": template,
        "correlation": correlation,
        "threshold_mask": threshold_mask,
        "blobs": blobs,
        "lattice": fit.lattice,
        "holes": holes,
        "good_holes": good_holes,
        "convolved_holes": convolved_holes,
        "sampled_holes": sampled_holes,
    }
