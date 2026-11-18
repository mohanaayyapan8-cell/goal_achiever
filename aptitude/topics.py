SECTIONS = {
    "quant": ("Quantitative Aptitude", ["Percentages", "Profit and Loss", "Simple and Compound Interest", "Time and Work",
                                        "Speed, Time and Distance", "Ratios and Proportions", "Averages", "Number Systems",
                                        "Probability", "Permutations and Combinations"]),
    "logical": ("Logical Reasoning", ["Number Series", "Coding and Decoding", "Blood Relations", "Directions",
                                      "Seating Arrangements", "Syllogisms", "Puzzles", "Analogies"]),
    "verbal": ("Verbal Ability", ["Grammar", "Tenses", "Articles", "Prepositions", "Subject-Verb Agreement", "Synonyms",
                                  "Antonyms", "Sentence Correction", "Reading Comprehension", "Error Detection"]),
}
SECTION_CHOICES = [(k, v[0]) for k, v in SECTIONS.items()]


def section_title(key):
    return SECTIONS[key][0]
