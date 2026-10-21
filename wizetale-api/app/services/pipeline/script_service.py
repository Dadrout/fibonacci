import logging
import math
import re

from pydantic import BaseModel, Field

from app.core.config import settings
from app.domain.models import (
    DraftGeneration,
    GenerationRequest,
    LearningOutcomes,
    ValidatedTopic,
    VideoScript,
)
from app.services.ai.provider_factory import get_text_provider

logger = logging.getLogger(__name__)

TARGET_NARRATION_WORDS_PER_MINUTE = 152
NARRATION_DURATION_TOLERANCE = 0.15


class TopicValidationUnavailable(RuntimeError):
    """Raised when a topic cannot be safety checked by the configured provider."""


class ScriptLengthUnavailable(RuntimeError):
    """Raised when the text provider cannot produce narration of the requested length."""


class TopicValidationPayload(BaseModel):
    normalized_topic: str
    pedagogical_framing: str
    valid: bool
    rejection_reason: str | None = None


class ScriptGenerationService:
    def __init__(self, text_service=None):
        self.text_service = text_service or get_text_provider()

    def validate_topic(self, request: GenerationRequest) -> ValidatedTopic:
        prompt = f"""
Validate and normalize this educational video topic.
Subject: {request.subject}
Topic: {request.topic}
Language: {request.language}

Accept only topics that can become a safe, meaningful educational video.
If valid, normalize the topic and provide a short pedagogical framing.
If invalid, set valid=false and explain why.
"""
        try:
            result = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="topic validation",
                schema=TopicValidationPayload,
                temperature=0.1,
                max_output_tokens=500,
                system_prompt="You are an educational content validator across language arts, math, science, history, geography, and philosophy.",
            )
        except Exception as error:
            logger.warning(
                "Topic validation failed; refusing to continue (%s).",
                type(error).__name__,
            )
            raise TopicValidationUnavailable(
                "Topic validation is temporarily unavailable."
            ) from error
        return ValidatedTopic(
            subject=request.subject,
            original_topic=request.topic,
            normalized_topic=result.normalized_topic,
            language=request.language,
            valid=result.valid,
            pedagogical_framing=result.pedagogical_framing,
            rejection_reason=result.rejection_reason,
        )

    def _normalize_topic(self, topic: str) -> str:
        normalized = " ".join((topic or "").split()).strip()
        if not normalized:
            return "General educational topic"
        return normalized[:160]

    def narration_word_range(self, target_duration_sec: int) -> tuple[int, int]:
        """Return a range calibrated to the measured narration pace."""
        target_words = round(
            target_duration_sec * TARGET_NARRATION_WORDS_PER_MINUTE / 60
        )
        # Story length is approximate: speaking pace varies by language and voice.
        minimum_words = max(1, math.ceil(target_words * (1 - NARRATION_DURATION_TOLERANCE)))
        maximum_words = math.floor(target_words * (1 + NARRATION_DURATION_TOLERANCE))
        return minimum_words, maximum_words

    def narration_length_is_valid(self, narration: str, target_duration_sec: int) -> bool:
        word_count = len(narration.split())
        minimum_words, maximum_words = self.narration_word_range(target_duration_sec)
        return minimum_words <= word_count <= maximum_words

    def estimated_narration_duration_sec(self, narration: str) -> int:
        """Estimate spoken duration from the actual narration, rather than the target."""
        word_count = len(narration.split())
        return max(
            1,
            round(word_count * 60 / TARGET_NARRATION_WORDS_PER_MINUTE),
        )

    def _narration_distance(self, narration: str, target_duration_sec: int) -> int:
        target_words = round(
            target_duration_sec * TARGET_NARRATION_WORDS_PER_MINUTE / 60
        )
        return abs(len(narration.split()) - target_words)

    def _closest_narration(
        self, narrations: list[str], target_duration_sec: int
    ) -> str:
        usable_narrations = [
            narration.strip() for narration in narrations if narration.strip()
        ]
        if not usable_narrations:
            return ""
        return min(
            usable_narrations,
            key=lambda narration: self._narration_distance(
                narration, target_duration_sec
            ),
        )

    def _cap_narration_to_duration(
        self, narration: str, target_duration_sec: int
    ) -> str:
        """Keep a best-effort narration from becoming much longer than requested."""
        _, maximum_words = self.narration_word_range(target_duration_sec)
        normalized = " ".join(narration.split())
        words = normalized.split()
        if len(words) <= maximum_words:
            return narration

        kept_sentences: list[str] = []
        kept_word_count = 0
        for sentence in re.split(r"(?<=[.!?…])\s+", normalized):
            sentence_word_count = len(sentence.split())
            if kept_word_count + sentence_word_count > maximum_words:
                break
            kept_sentences.append(sentence)
            kept_word_count += sentence_word_count

        # Prefer a clean sentence ending, but use the full allowance if one sentence
        # alone would otherwise make the narration much too short.
        minimum_words, _ = self.narration_word_range(target_duration_sec)
        if kept_word_count >= minimum_words:
            return " ".join(kept_sentences)

        clipped = " ".join(words[:maximum_words]).rstrip(" ,;:")
        if clipped and clipped[-1] not in ".!?…":
            clipped += "."
        return clipped

    def _length_correction_prompt(
        self,
        *,
        prompt: str,
        narration: str,
        target_duration_sec: int,
    ) -> str:
        minimum_words, maximum_words = self.narration_word_range(target_duration_sec)
        word_count = len(narration.split())
        return (
            f"{prompt}\n\nThe previous narration contained {word_count} words, outside "
            f"the required range of {minimum_words}–{maximum_words} words. Rewrite the "
            f"complete narration to approximately {round((minimum_words + maximum_words) / 2)} words, "
            f"within that range. Count words in full_narration only; aim for five to ten "
            "natural story sections with balanced narration. Keep it factual, clear, and "
            "age-appropriate; do not pad it with repetition.\n"
            f"Previous narration to revise:\n{narration}"
        )

    def _duration_prompt(self, request: GenerationRequest) -> str:
        minimum_words, maximum_words = self.narration_word_range(
            request.target_duration_sec
        )
        return (
            f"Target duration seconds: {request.target_duration_sec}\n"
            f"Narration length: {minimum_words}–{maximum_words} spoken words (about "
            f"{TARGET_NARRATION_WORDS_PER_MINUTE} words per minute, with a 15% tolerance). "
            "Aim near the middle of the range. The full narration controls the final video duration. "
            "The full_narration field must contain the complete story, not a summary. "
            "Count its words before returning and stay inside this range.\n"
        )

    def _grade_prompt(self, request: GenerationRequest) -> tuple[str, str]:
        if request.school_grade is not None:
            return (
                f"School grade: {request.school_grade}\n",
                f"- Adapt vocabulary and explanations for school grade {request.school_grade}.\n",
            )
        return (
            f"Learner age band: {request.grade_band}\n",
            f"- Adapt vocabulary and explanations for learners aged {request.grade_band}.\n",
        )

    def generate_script(
        self,
        *,
        request: GenerationRequest,
        validated_topic: ValidatedTopic,
        knowledge_context: str = "",
    ) -> VideoScript:
        grade_context, grade_requirement = self._grade_prompt(request)
        source_material = (
            "Reviewed source notes (use these as the factual basis; do not add unsupported details):\n"
            f"{knowledge_context}\n"
            if knowledge_context
            else ""
        )
        prompt = f"""
Generate a short educational video script.
Subject: {validated_topic.subject}
Normalized topic: {validated_topic.normalized_topic}
Pedagogical framing: {validated_topic.pedagogical_framing}
{source_material}
Language: {request.language}
{grade_context}
{self._duration_prompt(request)}

Requirements:
- Output language must be exactly {request.language}.
- Check subject-specific accuracy: arithmetic and reasoning for math, scientific explanations for science, evidence for history/geography, and fair attribution of viewpoints for philosophy and language arts.
- No markdown.
- Make the narration vivid and clear for an educational video.
{grade_requirement}
- Organize the story into 5–10 topic-driven narrative sections; choose the count from the topic's natural story beats.
- Populate script.sections with a heading and summary for each section, in narration order.
- estimated_duration_sec should be close to {request.target_duration_sec}.
"""
        try:
            script = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="script generation",
                schema=VideoScript,
                temperature=0.5,
                max_output_tokens=4000,
                system_prompt="You are an expert educational scriptwriter who produces clean structured JSON.",
            )
            if not script.full_narration.strip():
                raise ValueError("The script provider returned empty narration")
            candidates = [script]
            if not self.narration_length_is_valid(
                script.full_narration, request.target_duration_sec
            ):
                self._log_narration_length(
                    script.full_narration, request.target_duration_sec, "script generation"
                )
                corrected_script = self.text_service.generate_structured(
                    prompt=self._length_correction_prompt(
                        prompt=prompt,
                        narration=script.full_narration,
                        target_duration_sec=request.target_duration_sec,
                    ),
                    operation_name="script length correction",
                    schema=VideoScript,
                    temperature=0.3,
                    max_output_tokens=4000,
                    system_prompt="You are an expert educational scriptwriter who produces clean structured JSON.",
                )
                if corrected_script.full_narration.strip():
                    candidates.append(corrected_script)
            script = min(
                candidates,
                key=lambda candidate: self._narration_distance(
                    candidate.full_narration, request.target_duration_sec
                ),
            )
            capped_narration = self._cap_narration_to_duration(
                script.full_narration, request.target_duration_sec
            )
            if capped_narration != script.full_narration:
                logger.warning(
                    "Capped overlong narration for target duration: words=%d target_max=%d.",
                    len(script.full_narration.split()),
                    self.narration_word_range(request.target_duration_sec)[1],
                )
                script = script.model_copy(
                    update={"full_narration": capped_narration}
                )
            if not self.narration_length_is_valid(
                script.full_narration, request.target_duration_sec
            ):
                self._log_narration_length(
                    script.full_narration,
                    request.target_duration_sec,
                    "best-effort script generation",
                )
            return script.model_copy(
                update={
                    "estimated_duration_sec": self.estimated_narration_duration_sec(
                        script.full_narration
                    )
                }
            )
        except ScriptLengthUnavailable:
            raise
        except Exception:
            logger.warning(
                "Structured script generation failed for topic '%s'. Falling back to plain-text script mode.",
                validated_topic.normalized_topic,
            )
            return self._fallback_plain_script(request, validated_topic)

    def generate_draft(
        self,
        *,
        request: GenerationRequest,
        validated_topic: ValidatedTopic,
        knowledge_context: str = "",
    ) -> DraftGeneration:
        grade_context, grade_requirement = self._grade_prompt(request)
        source_material = (
            "Reviewed source notes (use these as the factual basis; do not add unsupported details):\n"
            f"{knowledge_context}\n"
            if knowledge_context
            else ""
        )
        prompt = f"""
Create an editable educational video draft and its learning check in one response.
Subject: {validated_topic.subject}
Normalized topic: {validated_topic.normalized_topic}
Pedagogical framing: {validated_topic.pedagogical_framing}
{source_material}
Language: {request.language}
{grade_context}
{self._duration_prompt(request)}

Requirements:
{grade_requirement}- Adapt the quiz for learners at the same level as the narration.
- Keep every factual claim supported by the source notes when provided.
- Organize the story into 5–10 topic-driven narrative sections; choose the count from the topic's natural story beats.
- Populate script.sections with a heading and summary for each section, in narration order.
- Make the recap concise and derive exactly three multiple-choice questions from the narration.
- Give each question 3 or 4 options, one correct answer, and a short explanation.
- Return structured data only, with no markdown.
"""
        try:
            result = self.text_service.generate_structured(
                prompt=prompt,
                operation_name="script and learning draft",
                schema=DraftGeneration,
                temperature=0.4,
                max_output_tokens=5400,
                system_prompt=(
                    "You are an expert educational scriptwriter. Produce accurate, age-aware "
                    "narration and a comprehension check grounded only in the supplied facts."
                ),
            )
        except Exception:
            logger.warning(
                "Combined draft generation failed for topic '%s'; using separate recovery calls.",
                validated_topic.normalized_topic,
            )
            script = self.generate_script(
                request=request,
                validated_topic=validated_topic,
                knowledge_context=knowledge_context,
            )
            outcomes = self.generate_learning_outcomes(
                topic=validated_topic.normalized_topic,
                narration=script.full_narration,
                language=request.language,
                grade_band=request.grade_band,
            )
            return DraftGeneration(script=script, learning_outcomes=outcomes)

        if not result.script.full_narration.strip():
            raise ValueError("The script provider returned empty narration")
        candidates = [result]
        for correction_index in range(2):
            best_result = min(
                candidates,
                key=lambda candidate: self._narration_distance(
                    candidate.script.full_narration,
                    request.target_duration_sec,
                ),
            )
            if self.narration_length_is_valid(
                best_result.script.full_narration, request.target_duration_sec
            ):
                break
            self._log_narration_length(
                best_result.script.full_narration,
                request.target_duration_sec,
                "script and learning draft"
                if correction_index == 0
                else "script and learning draft correction",
            )
            corrected_result = self.text_service.generate_structured(
                prompt=self._length_correction_prompt(
                    prompt=prompt,
                    narration=best_result.script.full_narration,
                    target_duration_sec=request.target_duration_sec,
                ),
                operation_name=(
                    "script and learning draft length correction "
                    f"{correction_index + 1}"
                ),
                schema=DraftGeneration,
                temperature=0.3,
                max_output_tokens=7000,
                system_prompt=(
                    "You are an expert educational scriptwriter. Produce accurate, age-aware "
                    "narration and a comprehension check grounded only in the supplied facts."
                ),
            )
            if corrected_result.script.full_narration.strip():
                candidates.append(corrected_result)

        result = min(
            candidates,
            key=lambda candidate: self._narration_distance(
                candidate.script.full_narration, request.target_duration_sec
            ),
        )
        capped_narration = self._cap_narration_to_duration(
            result.script.full_narration, request.target_duration_sec
        )
        narration_was_capped = capped_narration != result.script.full_narration
        if narration_was_capped:
            logger.warning(
                "Capped overlong draft narration for target duration: words=%d target_max=%d.",
                len(result.script.full_narration.split()),
                self.narration_word_range(request.target_duration_sec)[1],
            )
            result = result.model_copy(
                update={
                    "script": result.script.model_copy(
                        update={"full_narration": capped_narration}
                    )
                }
            )
        if not self.narration_length_is_valid(
            result.script.full_narration, request.target_duration_sec
        ):
            self._log_narration_length(
                result.script.full_narration,
                request.target_duration_sec,
                "best-effort script and learning draft",
            )

        result = result.model_copy(
            update={
                "script": result.script.model_copy(
                    update={
                        "estimated_duration_sec": self.estimated_narration_duration_sec(
                            result.script.full_narration
                        )
                    }
                )
            }
        )

        if narration_was_capped:
            try:
                outcomes = self.generate_learning_outcomes(
                    topic=validated_topic.normalized_topic,
                    narration=result.script.full_narration,
                    language=request.language,
                    grade_band=request.grade_band,
                )
                result = result.model_copy(update={"learning_outcomes": outcomes})
            except Exception:
                logger.warning(
                    "Could not refresh learning outcomes after shortening a long draft."
                )
        return result

    def _log_narration_length(
        self, narration: str, target_duration_sec: int, operation: str
    ) -> None:
        minimum_words, maximum_words = self.narration_word_range(target_duration_sec)
        logger.warning(
            "Narration length outside target during %s: words=%d target=%d-%d.",
            operation,
            len(narration.split()),
            minimum_words,
            maximum_words,
        )

    def _fallback_plain_script(
        self,
        request: GenerationRequest,
        validated_topic: ValidatedTopic,
    ) -> VideoScript:
        grade_context, grade_requirement = self._grade_prompt(request)
        plain_prompt = f"""
Write a complete educational narration for a short video.
Subject: {validated_topic.subject}
Topic: {validated_topic.normalized_topic}
Language: {request.language}
{grade_context}
{self._duration_prompt(request)}

Rules:
- {grade_requirement.strip().lstrip('- ')}
- Return plain narration text only.
- No markdown.
- Keep it factual and coherent.
"""
        narration = self.text_service.generate_text(
            prompt=plain_prompt,
            operation_name="script generation fallback",
            temperature=0.5,
            max_output_tokens=4000,
            system_prompt="You are an educational narrator.",
        ).strip()
        if not narration:
            narration = (
                f"This lesson explores {validated_topic.normalized_topic}. "
                "We examine causes, key events, and historical impact."
            )

        narrations = [narration]
        if not self.narration_length_is_valid(narration, request.target_duration_sec):
            minimum_words, maximum_words = self.narration_word_range(
                request.target_duration_sec
            )
            corrected_narration = self.text_service.generate_text(
                prompt=(
                    f"{plain_prompt}\nThe previous narration was too short or too long. "
                    f"Rewrite it as {minimum_words}–{maximum_words} words, without repetition."
                ),
                operation_name="script generation fallback length correction",
                temperature=0.3,
                max_output_tokens=4000,
                system_prompt="You are an educational narrator.",
            ).strip()
            if corrected_narration:
                narrations.append(corrected_narration)
        narration = self._closest_narration(narrations, request.target_duration_sec)
        if not narration:
            narration = (
                f"This lesson explores {validated_topic.normalized_topic}. "
                "We examine its main ideas, important examples, and why they matter."
            )
        narration = self._cap_narration_to_duration(
            narration, request.target_duration_sec
        )

        first_sentence_match = re.split(r"(?<=[.!?])\s+", narration, maxsplit=1)
        hook = first_sentence_match[0][:220] if first_sentence_match else narration[:220]

        return VideoScript(
            title=validated_topic.normalized_topic[:120],
            hook=hook,
            sections=[],
            full_narration=narration,
            estimated_duration_sec=self.estimated_narration_duration_sec(narration),
        )

    def generate_learning_outcomes(
        self,
        *,
        topic: str,
        narration: str,
        language: str,
        grade_band: str,
    ) -> LearningOutcomes:
        return self.text_service.generate_structured(
            prompt=(
                "Create a concise recap and exactly three multiple-choice comprehension questions "
                f"in {language} for learners aged {grade_band}. Use only facts supported by the narration. "
                "Each question must have 3 or 4 options, one correct option, and a short explanation.\n"
                f"Topic: {topic}\nNarration:\n{narration}"
            ),
            operation_name="recap and comprehension quiz",
            schema=LearningOutcomes,
            temperature=0.2,
            max_output_tokens=1800,
            system_prompt="You create accurate learning checks from supplied lesson narration.",
        )

    def enhance_prompt(self, *, description: str, language: str) -> str:
        prompt = f"""
Enhance this educational video idea for a scriptwriter.
Language: {language}
Description: {description}

Return only the improved description in {language}. Keep it concise but vivid.
"""
        return self.text_service.generate_text(
            prompt=prompt,
            operation_name="prompt enhancement",
            temperature=0.8,
            max_output_tokens=800,
            system_prompt="You are a creative but disciplined educational video ideation assistant.",
        )


script_generation_service = ScriptGenerationService()
