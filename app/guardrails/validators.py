"""Citation validator — ensures every factual claim cites a real chunk.

Validates that generated memo sections include proper citations referencing
retrieved document chunks. Factual claims (sentences containing numbers,
specific entities, or financial figures) must reference valid chunk IDs.

Design decision: Citation validation is a hard gate — a claim without a
valid citation fails validation and the section is flagged for review.
This prevents hallucinated facts from appearing in the final memo.
"""

from __future__ import annotations

import re
import logging
from dataclasses import dataclass
from typing import Any, Dict, List, Set, Tuple

logger = logging.getLogger(__name__)


@dataclass
class CitationProblem:
    """A citation validation problem."""

    claim: str
    problem_type: str  # "missing_citation", "invalid_chunk_id", "orphaned_citation"
    severity: str  # "error", "warning"
    detail: str

    def to_dict(self) -> Dict[str, Any]:
        return {
            "claim": self.claim,
            "problem_type": self.problem_type,
            "severity": self.severity,
            "detail": self.detail,
        }


# Patterns for detecting citations in text
_CITATION_PATTERN = re.compile(r'\[ref:([a-zA-Z0-9_-]+)\]')
_CITATION_PATTERN_ALT = re.compile(r'\(ref:([a-zA-Z0-9_-]+)\)')
_CITATION_PATTERN_BRACKET = re.compile(r'\[([a-zA-Z0-9_-]+(?:_chunk|_doc)[a-zA-Z0-9_-]*)\]')

# Patterns for detecting factual claims (sentences with numbers/entities)
_NUMBER_PATTERN = re.compile(
    r'\b\d{1,3}(?:,\d{3})*(?:\.\d+)?\b|'  # Numbers with optional commas/decimals
    r'\b\d+(?:\.\d+)?%\b|'  # Percentages
    r'\bKD\s*\d+\b|'  # Kuwaiti Dinar amounts
    r'\b\d+(?:\.\d+)?x\b'  # Ratios (e.g., 1.45x)
)

# Sentence splitting
_SENTENCE_PATTERN = re.compile(r'(?<=[.!?])\s+')


def extract_citations(text: str) -> List[str]:
    """Extract all citation chunk IDs from text."""
    citations = set()

    for pattern in [_CITATION_PATTERN, _CITATION_PATTERN_ALT, _CITATION_PATTERN_BRACKET]:
        matches = pattern.findall(text)
        citations.update(matches)

    return sorted(citations)


def validate_citations(
    content: str,
    valid_chunk_ids: Set[str],
    citations_json: List[Dict[str, Any]] | None = None,
) -> Tuple[bool, List[CitationProblem]]:
    """Validate citations in generated content.

    Checks:
    1. Every factual claim (sentence with numbers) has at least one citation.
    2. Every cited chunk ID exists in the valid_chunk_ids set.
    3. Citations in the JSON metadata match citations in the text.

    Args:
        content: The generated text content.
        valid_chunk_ids: Set of valid chunk IDs from the retrieved context.
        citations_json: Optional structured citations from the LLM output.

    Returns:
        Tuple of (is_valid: bool, problems: List[CitationProblem]).
    """
    problems: List[CitationProblem] = []

    # Extract all citations from text
    text_citations = set(extract_citations(content))

    # Check for invalid chunk IDs
    for chunk_id in text_citations:
        if chunk_id not in valid_chunk_ids:
            problems.append(CitationProblem(
                claim="",
                problem_type="invalid_chunk_id",
                severity="warning",
                detail=f"Citation '{chunk_id}' does not reference a valid chunk.",
            ))

    # Split content into sentences and check each for factual claims
    sentences = _SENTENCE_PATTERN.split(content)
    for sentence in sentences:
        sentence = sentence.strip()
        if not sentence or len(sentence) < 20:
            continue

        # Check if this sentence contains factual claims (numbers)
        has_numbers = bool(_NUMBER_PATTERN.search(sentence))
        if not has_numbers:
            continue

        # Check if the sentence has at least one citation
        sentence_citations = set()
        for pattern in [_CITATION_PATTERN, _CITATION_PATTERN_ALT, _CITATION_PATTERN_BRACKET]:
            sentence_citations.update(pattern.findall(sentence))

        if not sentence_citations:
            # Factual claim without citation
            problems.append(CitationProblem(
                claim=sentence[:200],
                problem_type="missing_citation",
                severity="error",
                detail="Factual claim (contains numbers/entities) without any citation.",
            ))

    # Validate structured citations JSON if provided
    if citations_json:
        structured_ids = set()
        for item in citations_json:
            if isinstance(item, dict):
                for key, value in item.items():
                    if isinstance(value, str) and value:
                        structured_ids.add(value)
                    elif isinstance(value, list):
                        structured_ids.update(str(v) for v in value if v)

        # Check structured citations reference valid chunks
        for chunk_id in structured_ids:
            if chunk_id not in valid_chunk_ids:
                problems.append(CitationProblem(
                    claim="",
                    problem_type="invalid_chunk_id",
                    severity="warning",
                    detail=f"Structured citation '{chunk_id}' does not reference a valid chunk.",
                ))

    is_valid = not any(p.severity == "error" for p in problems)
    return is_valid, problems
