"""
Multi-phase shipper aggregation.

Ascent often ships a single job across multiple PDFs (PH1 structural,
PH3 mezzanine, PH4 panels, etc.). This module combines them into one
logical shipper dataset for comparison against the Final Drawings.
"""

from pathlib import Path
from typing import List, Dict, Any, Optional
from chubby_checker.parsers.shipper_parser import ShipperParser
from chubby_checker.models.piece import Piece


class MultiPhaseShipper:
    """Aggregate multiple phase shippers into a single dataset."""

    def __init__(self, pdf_paths: List[str | Path]):
        self.pdf_paths = [Path(p) for p in pdf_paths]
        self.phases: List[Dict[str, Any]] = []
        self.aggregated: Dict[str, Any] = {}

    def parse(self) -> Dict[str, Any]:
        """Parse every phase and merge results."""
        combined_categories: Dict[str, List[Piece]] = {}
        combined_accessories: Dict[str, int] = {
            "sliding_clips": 0,
            "backup_plates_24": 0,
            "backup_plates_18": 0,
            "thermal_blocks": 0,
            "clip_screws": 0,
            "hi_eave_plates": 0,
            "hi_rake_supports": 0,
        }
        combined_coverage: Dict[str, int] = {}
        combined_weights: Dict[str, float] = {}
        total_weight = 0.0
        job_number = ""
        phase_names: List[str] = []

        for path in self.pdf_paths:
            parser = ShipperParser(path)
            # Support both old and new parser return styles
            result = parser.parse()

            # Newer parsers return a rich dict; older ones return categories only
            if isinstance(result, dict) and "categories" in result:
                cats = result.get("categories", {})
                accessories = result.get("ss_accessories", parser.get_ss_accessories())
                coverage = result.get("panel_coverage", {})
                summary = result.get("summary")
                weights = result.get("summary_weights", parser.get_summary_weights())
            else:
                cats = result if isinstance(result, dict) else {}
                accessories = parser.get_ss_accessories()
                coverage = {}
                summary = None
                weights = parser.get_summary_weights()

            phase_label = path.stem
            phase_names.append(phase_label)

            # Merge categories / pieces
            for cat, pieces in cats.items():
                combined_categories.setdefault(cat, []).extend(pieces)

            # Sum accessories
            for k, v in accessories.items():
                combined_accessories[k] = combined_accessories.get(k, 0) + v

            # Sum panel coverage
            for width, qty in coverage.items():
                combined_coverage[width] = combined_coverage.get(width, 0) + qty

            # Sum weights
            for cat, wt in weights.items():
                combined_weights[cat] = combined_weights.get(cat, 0.0) + wt

            if summary and getattr(summary, "total_weight", 0):
                total_weight += summary.total_weight
            if summary and getattr(summary, "job_number", "") and not job_number:
                job_number = summary.job_number

            self.phases.append({
                "path": str(path),
                "label": phase_label,
                "categories": cats,
                "accessories": accessories,
                "coverage": coverage,
            })

        # Build a simple summary object compatible with the engine
        class _Summary:
            pass
        summary_obj = _Summary()
        summary_obj.job_number = job_number
        summary_obj.phase = " + ".join(phase_names)
        summary_obj.total_weight = total_weight

        self.aggregated = {
            "summary": summary_obj,
            "categories": combined_categories,
            "ss_accessories": combined_accessories,
            "panel_coverage": combined_coverage,
            "summary_weights": combined_weights,
            "phases": self.phases,
            "phase_count": len(self.pdf_paths),
        }
        return self.aggregated

    def get_phase_summary(self) -> str:
        lines = [f"Multi-phase job ({len(self.pdf_paths)} shippers):"]
        for p in self.phases:
            lines.append(f"  - {p['label']}")
        return "\n".join(lines)
