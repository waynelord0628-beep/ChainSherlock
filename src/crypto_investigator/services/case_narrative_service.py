from __future__ import annotations

from datetime import datetime, timezone

from pydantic import BaseModel, Field

from crypto_investigator.cases.results import CaseResult, ReviewStatus


class CaseNarrativeSection(BaseModel):
    section_id: str
    title: str
    paragraphs: list[str] = Field(default_factory=list)


class CaseNarrativeResult(BaseModel):
    case_id: str
    generated_at: datetime = Field(default_factory=lambda: datetime.now(timezone.utc))
    deterministic: bool = True
    review_status: ReviewStatus = ReviewStatus.NOT_REVIEWED
    sections: list[CaseNarrativeSection]
    limitations: list[str] = Field(default_factory=list)


class CaseNarrativeService:
    def compose(self, result: CaseResult) -> CaseNarrativeResult:
        facts = [
            f"{item.category}: {item.statement}" for item in result.confirmed_facts
        ] or ["No confirmed deterministic facts are available."]
        observations = [
            item.factual_statement for item in result.deterministic_observations
        ] or ["No deterministic observations are available."]
        candidates = [
            f"Candidate ({item.candidate_type.value}): {item.statement}"
            for item in result.candidate_interpretations
        ] or ["No candidate interpretations are available."]
        questions = [item.question for item in result.unresolved_questions] or [
            "No unresolved question was generated."
        ]
        followups = [
            item.description for item in result.recommended_follow_ups
        ] or ["No follow-up recommendation was generated."]
        goals = [
            str(item.get("title", item.get("goal_type", "Untitled goal")))
            for item in result.investigation_goals
        ] or ["No investigation goal is available."]
        limitations = result.limitations or [
            "No additional limitations were recorded."
        ]
        return CaseNarrativeResult(
            case_id=result.case_id,
            sections=[
                CaseNarrativeSection(
                    section_id="case_brief",
                    title="Case Brief",
                    paragraphs=[
                        f"Case: {result.title}",
                        f"Data completeness: {result.completeness}",
                    ],
                ),
                CaseNarrativeSection(
                    section_id="goals",
                    title="Investigation Goals",
                    paragraphs=goals,
                ),
                CaseNarrativeSection(
                    section_id="confirmed_facts",
                    title="Confirmed Facts",
                    paragraphs=facts,
                ),
                CaseNarrativeSection(
                    section_id="observations",
                    title="Deterministic Observations",
                    paragraphs=observations,
                ),
                CaseNarrativeSection(
                    section_id="candidate_interpretations",
                    title="Candidate Interpretations",
                    paragraphs=candidates,
                ),
                CaseNarrativeSection(
                    section_id="unresolved_questions",
                    title="Unresolved Questions",
                    paragraphs=questions,
                ),
                CaseNarrativeSection(
                    section_id="recommended_follow_ups",
                    title="Recommended Follow-up",
                    paragraphs=followups,
                ),
                CaseNarrativeSection(
                    section_id="limitations",
                    title="Limitations",
                    paragraphs=limitations,
                ),
            ],
            limitations=list(result.limitations),
        )
