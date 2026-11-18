"""Default curriculum copied into each new user's account.
Users can rename, delete or extend all of it."""

DEFAULT_CURRICULUM = [
    ("Technical Skills", "Core tools and technologies for technical roles.", [
        ("Python", [
            "Introduction to Python", "Variables and Data Types", "Operators", "Conditional Statements", "Loops",
            "Functions", "Lists", "Tuples", "Sets", "Dictionaries", "Strings", "Exception Handling",
            "File Handling", "OOP Concepts", "Modules and Packages", "Basic Projects"]),
        ("SQL", [
            "Introduction to Databases", "SELECT and Filtering", "Sorting and Limiting", "Aggregate Functions",
            "GROUP BY and HAVING", "Joins", "Subqueries", "Set Operations", "Constraints and Keys",
            "Window Functions", "Views and Indexes", "Normalization"]),
        ("Excel", [
            "Interface and Basics", "Formulas and Functions", "Lookup Functions", "Conditional Formatting",
            "Sorting and Filtering", "Pivot Tables", "Charts", "Data Cleaning", "Data Validation", "Dashboards"]),
        ("Power BI", [
            "Introduction and Interface", "Importing Data", "Power Query Basics", "Data Modeling", "DAX Basics",
            "Visuals", "Filters and Slicers", "Building a Dashboard", "Publishing and Sharing"]),
        ("Tableau", [
            "Introduction to Tableau", "Connecting to Data", "Dimensions and Measures", "Charts",
            "Calculated Fields", "Filters and Parameters", "Dashboards and Stories"]),
        ("Django", [
            "Introduction and Setup", "Project Structure", "Models and ORM", "Views, URLs and Templates", "Forms",
            "Authentication", "Admin Site", "Static Files", "Testing", "Deployment Basics"]),
        ("Prompt Engineering", [
            "What Is Prompt Engineering", "Writing Clear Prompts", "Roles and Context", "Few-shot Examples",
            "Step-by-step Reasoning", "Output Formatting", "Evaluating and Improving Prompts",
            "Safe and Responsible Use"]),
        ("Git and GitHub", [
            "Version Control Basics", "Installing and Configuring Git", "Commits and History", "Branches",
            "Merging and Conflicts", "Remote Repositories", "Pull Requests", "gitignore and Workflows"]),
        ("Cloud Computing Basics", [
            "What Is Cloud Computing", "IaaS, PaaS and SaaS", "Deployment Models", "Virtual Machines",
            "Storage Services", "Networking Basics", "Security and Pricing Basics"]),
        ("AI and ML Basics", [
            "What Are AI and ML", "Types of Machine Learning", "Data Preparation", "Regression", "Classification",
            "Model Evaluation", "Overfitting and Underfitting", "Introduction to Neural Networks",
            "Ethics and Bias"]),
    ]),
    ("Aptitude", "Quantitative, reasoning and verbal skills for placement tests.", [
        ("Quantitative Aptitude", [
            "Percentages", "Profit and Loss", "Simple and Compound Interest", "Time and Work",
            "Speed, Time and Distance", "Ratios and Proportions", "Averages", "Number Systems", "Probability",
            "Permutations and Combinations"]),
        ("Logical Reasoning", [
            "Number Series", "Coding and Decoding", "Blood Relations", "Directions", "Seating Arrangements",
            "Syllogisms", "Puzzles", "Analogies"]),
        ("Verbal Ability", [
            "Grammar", "Tenses", "Articles", "Prepositions", "Subject-Verb Agreement", "Synonyms", "Antonyms",
            "Sentence Correction", "Reading Comprehension", "Error Detection"]),
    ]),
    ("Data Structures and Algorithms", "Problem-solving fundamentals for coding interviews.", [
        ("Arrays", ["Array Basics and Traversal", "Insertion and Deletion", "Two-pointer Technique", "Prefix Sums",
                    "Sliding Window", "Kadane's Algorithm"]),
        ("Strings", ["String Basics", "Palindromes and Reversal", "Anagrams", "Substring Search",
                     "Frequency Counting"]),
        ("Searching", ["Linear Search", "Binary Search", "Binary Search Variations"]),
        ("Sorting", ["Bubble Sort", "Selection Sort", "Insertion Sort", "Merge Sort", "Quick Sort",
                     "Complexity Comparison"]),
        ("Linked Lists", ["Singly Linked List", "Insertion and Deletion", "Reversing a List", "Cycle Detection",
                          "Doubly Linked List"]),
        ("Stacks", ["Stack Basics", "Balanced Parentheses", "Next Greater Element", "Expression Evaluation"]),
        ("Queues", ["Queue Basics", "Circular Queue", "Deque", "Queue using Stacks"]),
        ("Recursion", ["Recursion Basics", "Factorial and Fibonacci", "Backtracking Introduction",
                       "Recursion vs Iteration"]),
        ("Basic Algorithms", ["Time and Space Complexity", "Greedy Basics", "Dynamic Programming Basics",
                              "Hashing Basics"]),
    ]),
    ("Professional Development", "Resume, interviews and communication.", [
        ("Resume Building", ["Resume Structure and Sections", "Writing Achievement Bullets",
                             "Projects and Skills Sections", "Final Review"]),
        ("ATS Resume Optimization", ["How ATS Software Works", "Keywords from Job Descriptions",
                                     "ATS-friendly Formatting"]),
        ("LinkedIn Profile Development", ["Headline and About Section", "Experience and Skills",
                                          "Networking Basics"]),
        ("HR Interview Preparation", ["Tell Me About Yourself", "Strengths and Weaknesses",
                                      "Behavioral Questions (STAR)", "Salary and Expectation Questions",
                                      "Questions to Ask the Interviewer"]),
        ("Technical Interview Preparation", ["Explaining Your Projects", "Core CS Fundamentals",
                                             "Problem-solving Approach", "Mock Interviews"]),
        ("English Communication", ["Sentence Building", "Vocabulary Building", "Speaking Fluency Practice",
                                   "Listening Practice", "Professional Email Writing"]),
    ]),
]
