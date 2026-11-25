"""Tests for the rule checks (src/reviewer/pipeline/rules.py) and finding merge."""

from src.reviewer.models import MCQ, Finding
from src.reviewer.pipeline.judge import merge_findings
from src.reviewer.pipeline.rules import check_rules, normalise


def mcq(question="What is it?", answer="Stamen", distractors=("Stigma", "Petal", "Sepal")):
    return MCQ(id="t", question=question, correct_answer=answer,
               distractors=list(distractors), source="test")


def kinds(findings):
    return {(f.target, f.issue_type, f.severity) for f in findings}


def test_normalise_drops_case_punctuation_articles_and_plurals():
    assert normalise("The Proteins.") == normalise("protein")
    assert normalise("Bacteria") == "bacteria"
    assert normalise("Glass") == "glass"


def test_clean_question_has_no_findings():
    assert check_rules(mcq()) == []


def test_duplicate_distractors():
    found = kinds(check_rules(mcq(answer="Cells", distractors=["Water", "Proteins", "Protein"])))
    assert ("distractor:2", "duplicate", "low") in found


def test_distractor_equal_to_answer_is_also_correct_high():
    found = kinds(check_rules(mcq(answer="Water vapor", distractors=["the water vapour", "Ice", "Water Vapor."])))
    assert ("distractor:2", "also_correct", "high") in found


def test_length_cue():
    found = kinds(check_rules(mcq(answer="Store water and maintain cell pressure",
                                  distractors=["Use water", "Heat", "Make sugar"])))
    assert ("question", "answer_cue", "medium") in found


def test_no_length_cue_when_one_distractor_is_long():
    found = kinds(check_rules(mcq(answer="Store water and maintain cell pressure",
                                  distractors=["Use water", "Heat", "Make sugar inside the chloroplast"])))
    assert ("question", "answer_cue", "medium") not in found


def test_grammar_cue_an():
    found = kinds(check_rules(mcq(question="A cell's powerhouse is an", answer="organelle",
                                  distractors=["nucleus", "protein", "membrane"])))
    assert ("question", "answer_cue", "medium") in found


def test_grammar_cue_a():
    found = kinds(check_rules(mcq(question="Water is a", answer="compound",
                                  distractors=["element", "atom", "ion"])))
    assert ("question", "answer_cue", "medium") in found


def test_no_grammar_cue_when_a_distractor_also_fits():
    found = kinds(check_rules(mcq(question="A cell's powerhouse is an", answer="organelle",
                                  distractors=["enzyme", "protein", "membrane"])))
    assert ("question", "answer_cue", "medium") not in found


def test_all_of_the_above():
    found = kinds(check_rules(mcq(distractors=["Stigma", "Petal", "All of the above"])))
    assert ("distractor:2", "ambiguous_question", "low") in found


def test_merge_keeps_highest_severity_and_all_layers():
    findings = [
        Finding(target="distractor:0", issue_type="also_correct", severity="medium",
                reason="similar", detected_by=["similarity"]),
        Finding(target="distractor:0", issue_type="also_correct", severity="high",
                reason="LLM reason", detected_by=["llm"]),
        Finding(target="distractor:0", issue_type="also_correct", severity="high",
                reason="rule reason", detected_by=["rules"]),
    ]
    [merged] = merge_findings(findings)
    assert merged.severity == "high"
    assert merged.detected_by == ["rules", "similarity", "llm"]
    assert merged.reason == "LLM reason"


# ---------- review fixes (10-question test paper) ----------

def test_grammar_cue_with_trailing_blank():
    found = kinds(check_rules(mcq(question="The smallest unit of a chemical element is called an ________.",
                                  answer="atom", distractors=["molecule", "compound", "mixture"])))
    assert ("question", "answer_cue", "medium") in found


def test_numbers_with_units_are_detected():
    from src.reviewer.pipeline.similarity import is_mainly_number
    assert all(is_mainly_number(t) for t in ["100 °C", "50 °C", "29", "3.5 m/s", "Two"])
    assert not any(is_mainly_number(t) for t in ["Oxygen", "kg m/s^2", "Carbon dioxide"])


def test_llm_never_creates_answer_cue_or_duplicate():
    from src.reviewer.pipeline.judge import JudgeOutput, OptionVerdict, verdict_to_findings
    output = JudgeOutput(question_ambiguous=False, question_reason="", answer_key_agrees=True,
                         answer_key_reason="", options=[
                             OptionVerdict(option_index=0, is_also_correct="no", plausibility=4,
                                           issue_type="answer_cue", reason="tempting"),
                             OptionVerdict(option_index=1, is_also_correct="no", plausibility=3,
                                           issue_type="duplicate", reason="same as option 0")])
    assert verdict_to_findings(output, 3) == []


def test_each_option_shows_one_finding_highest_severity():
    findings = [
        Finding(target="distractor:2", issue_type="duplicate", severity="low", reason="dup", detected_by=["llm"]),
        Finding(target="distractor:2", issue_type="also_correct", severity="high", reason="O2 is oxygen",
                detected_by=["llm"]),
        Finding(target="question", issue_type="answer_cue", severity="medium", reason="long", detected_by=["rules"]),
    ]
    merged = merge_findings(findings)
    on_option = [f for f in merged if f.target == "distractor:2"]
    assert len(on_option) == 1 and on_option[0].issue_type == "also_correct"
    assert any(f.target == "question" for f in merged)


def test_reasons_use_letters_not_indices():
    from src.reviewer.pipeline.judge import letters_in_reason, option_letters
    letters = option_letters(3, answer_position=0)          # answer is A → distractors are B, C, D
    assert letters == ["B", "C", "D"]
    assert letters_in_reason("Option 0 (Iron) is also correct, unlike distractor 2.", letters) == \
        "option B (Iron) is also correct, unlike option D."
