"""External reading links (main pages of trusted sites). Shown on every topic page."""

DEFAULT_LINKS = [
    ("GeeksforGeeks", "https://www.geeksforgeeks.org/"),
    ("W3Schools", "https://www.w3schools.com/"),
]

REFERENCES = {
    "python": [("Official Python tutorial", "https://docs.python.org/3/tutorial/"),
               ("W3Schools Python", "https://www.w3schools.com/python/"),
               ("GeeksforGeeks", "https://www.geeksforgeeks.org/")],
    "sql": [("W3Schools SQL", "https://www.w3schools.com/sql/"), ("GeeksforGeeks", "https://www.geeksforgeeks.org/")],
    "excel": [("W3Schools Excel", "https://www.w3schools.com/excel/"), ("Microsoft Learn", "https://learn.microsoft.com/")],
    "power bi": [("Microsoft Learn: Power BI", "https://learn.microsoft.com/en-us/power-bi/")],
    "tableau": [("Tableau training", "https://www.tableau.com/learn/training")],
    "django": [("Django documentation", "https://docs.djangoproject.com/"),
               ("W3Schools Django", "https://www.w3schools.com/django/")],
    "git and github": [("Git documentation", "https://git-scm.com/doc"), ("W3Schools Git", "https://www.w3schools.com/git/")],
    "cloud computing basics": [("Microsoft Learn", "https://learn.microsoft.com/"), ("GeeksforGeeks", "https://www.geeksforgeeks.org/")],
}


def links_for(technology_name):
    return REFERENCES.get(technology_name.lower(), DEFAULT_LINKS)
