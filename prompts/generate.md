You write wrong options (distractors) for a science MCQ.

Question: {question}
Verified correct answer (do not change, do not paraphrase): {correct_answer}
Other options that stay: {kept_options}
Distractors to replace (index: text, problem): {weak_distractors}
Candidates already rejected for being unsafe (do not repeat them): {rejected}

For each distractor to replace, give 3 candidates. Each candidate must:
- be scientifically WRONG for this question
- reflect a real, common student misconception (state it in "misconception")
- match the answer's type and format (number for number, organ for organ…)
- be of similar length to the answer
- not be a synonym or paraphrase of the answer, and not repeat an existing option
- not be "all of the above" or "none of the above"

Return JSON only, matching the schema.
