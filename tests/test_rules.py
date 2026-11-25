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
