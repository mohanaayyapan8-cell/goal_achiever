"""Ready-made questions for the default Python topics (original wording).

Every written question carries its own transparent rubric:
  points - key ideas an answer should mention (regex alternatives; any one match counts)
  checks - things the submitted CODE must (or must not) contain
Questions for other topics are built from generic templates (see services.py)."""


def pt(label, *patterns, must=True):
    return {"label": label, "any": list(patterns), "must": must}


def ck(label, pattern, must_not=False):
    return {"label": label, "pattern": pattern, "must_not": must_not}


def E(prompt, points, model, min_words=35, example=False):
    return {"type": "explain", "prompt": prompt, "points": points, "checks": [], "model_answer": model,
            "model_code": "", "min_words": min_words, "needs_example": example}


def O(code, expected):
    return {"type": "predict_output", "prompt": "What will this program print? Write the exact output.",
            "code": code, "expected_output": expected, "model_answer": expected, "model_code": "",
            "points": [], "checks": [], "min_words": 0, "needs_example": False}


def P(prompt, checks, model_code, points=(), model_text="", min_words=0, qtype="program"):
    return {"type": qtype, "prompt": prompt, "points": list(points), "checks": checks,
            "model_answer": model_text, "model_code": model_code, "min_words": min_words, "needs_example": False}


def D(prompt, buggy, checks, model_code, points, model_text, min_words=10):
    q = P(prompt, checks, model_code, points, model_text, min_words, qtype="debug")
    q["code"] = buggy
    return q


def X(prompt, code, points, model, min_words=30):
    return {"type": "explain_logic", "prompt": prompt, "code": code, "points": points, "checks": [],
            "model_answer": model, "model_code": "", "min_words": min_words, "needs_example": False}


WRITTEN = {"python": {
 "introduction to python": [
  E("What is Python, and why is it a good first programming language? Mention at least two features.",
    [pt("It is a high-level, interpreted language", r"interpret", r"high[- ]level"),
     pt("Simple, readable syntax", r"readab", r"simple", r"easy", r"english"),
     pt("Other strengths: libraries, community or portability", r"librar", r"communit", r"portab|cross[- ]platform", must=False),
     pt("Common uses (web, data, automation, AI)", r"\bweb\b", r"\bdata\b", r"automat", r"\bAI\b|machine learning", must=False)],
    "Python is a high-level, interpreted programming language. Its syntax is simple and readable, so beginners can focus on logic. It also has a huge community and many libraries, and it is used for web development, data analysis, automation and AI.", 30),
  O('print("Hello", "Python")\nprint("Line" + "2")', "Hello Python\nLine2"),
  P("Write a program that asks for the user's name and prints a greeting such as: Hello, Asha!",
    [ck("Reads the name with input()", r"input\s*\("), ck("Stores it in a variable", r"\w+\s*=\s*input\s*\("),
     ck("Prints the greeting with print()", r"print\s*\(")],
    'name = input("Your name: ")\nprint(f"Hello, {name}!")')],
 "variables and data types": [
  E("Explain what a variable is and describe four common data types with a short example of each.",
    [pt("A variable is a name that refers to a stored value", r"variable.*(name|stor|refer|hold|contain)", r"(name|stor|refer|hold|contain).*variable"),
     pt("int: whole numbers", r"\bint\b", r"integer", r"whole number"),
     pt("float: decimal numbers", r"\bfloat\b", r"decimal"),
     pt("str: text", r"\bstr\b", r"string", r"text"),
     pt("bool: True or False", r"\bbool", r"true.*false")],
    'A variable is a name that refers to a value stored in memory. Common data types are int for whole numbers such as 21, float for decimals such as 99.5, str for text such as "Asha", and bool for True or False. For example, age = 21 creates an int variable.', 35, True),
  O("x = 7\ny = 2\nprint(x / y)\nprint(type(x // y))", "3.5\n<class 'int'>"),
  D("This program should add 1 to the age typed by the user, but it crashes. Fix the code and explain the bug.",
    'age = input("Age: ")\nprint(age + 1)',
    [ck("Converts the value to a number with int()", r"int\s*\("), ck("Still reads the value with input()", r"input\s*\(")],
    'age = int(input("Age: "))\nprint(age + 1)',
    [pt("input() returns text (a string)", r"\bstr\b", r"string", r"text"), pt("It must be converted, for example with int()", r"int\s*\(", r"convert|cast")],
    "input() always returns a string, and a string cannot be added to the number 1. Converting it with int() fixes the error.")],
 "operators": [
  E("Explain the difference between /, // and % in Python with an example for each.",
    [pt("/ gives a float (true division)", r"/.*(float|decimal|true division)", r"(float|decimal|true division).*/"),
     pt("// gives the floor (whole-number) result", r"//.*(floor|whole|integer|quotient)", r"(floor|integer|whole).*//"),
     pt("% gives the remainder", r"remainder", r"modulo|modulus")],
    "The / operator performs true division and always returns a float, so 7 / 2 is 3.5. The // operator is floor division and returns the whole number part of the quotient, so 7 // 2 is 3. The % operator gives the remainder, so 7 % 2 is 1.", 30, True),
  O("print(17 // 5, 17 % 5, 2 ** 3)\nprint(not (3 > 2 and 1 > 2))", "3 2 8\nTrue"),
  P("Write a program that reads a whole number and prints whether it is even or odd.",
    [ck("Reads input", r"input\s*\("), ck("Converts it with int()", r"int\s*\("), ck("Uses % with 2", r"%\s*2"),
     ck("Uses if", r"\bif\b"), ck("Prints a result", r"print\s*\(")],
    'n = int(input("Number: "))\nif n % 2 == 0:\n    print("Even")\nelse:\n    print("Odd")')],
 "conditional statements": [
  E("Explain how if, elif and else work together. Why does the order of the conditions matter?",
    [pt("if runs its block when its condition is true", r"\bif\b.*(true|condition)"),
     pt("elif checks further conditions", r"elif"),
     pt("else handles the remaining case", r"\belse\b"),
     pt("Conditions are checked from top to bottom; only the first true block runs", r"top to bottom", r"in order", r"first (true|match)", r"only one", r"one after")],
    "An if statement runs its block when its condition is true. elif lets you check more conditions, and else runs when none of them were true. Python checks them from top to bottom and runs only the first block that is true, so the order matters: a broad condition placed first would hide the narrower ones.", 35),
  O('n = 15\nif n % 3 == 0:\n    print("Fizz")\nelif n % 5 == 0:\n    print("Buzz")\nelse:\n    print(n)', "Fizz"),
  P("Write a program that reads marks and prints grade A for 90 or more, B for 60 or more, otherwise C.",
    [ck("Reads input", r"input\s*\("), ck("Uses if", r"\bif\b"), ck("Uses elif", r"\belif\b"), ck("Uses else", r"\belse\b"),
     ck("Compares with 90", r">=?\s*90"), ck("Compares with 60", r">=?\s*60")],
    'marks = int(input("Marks: "))\nif marks >= 90:\n    print("A")\nelif marks >= 60:\n    print("B")\nelse:\n    print("C")')],
 "loops": [
  E("Explain the difference between a for loop and a while loop. When would you choose each?",
    [pt("for goes through a sequence or a range", r"\bfor\b.*(sequence|range|iterat|each|list|items?)"),
     pt("while repeats as long as a condition is true", r"\bwhile\b.*(condition|true|until)"),
     pt("for suits a known number of repeats; while suits an unknown number", r"(known|fixed|definite|number of (times|iterations))", r"(unknown|not known|until|indefinite)"),
     pt("A while loop needs its condition to change, otherwise it never ends", r"infinite|forever|never end|update|increment", must=False)],
    "A for loop goes through each item of a sequence or a range, so it is best when I know how many times to repeat. A while loop keeps repeating as long as its condition is true, so it suits cases where the number of repetitions is not known in advance. In a while loop the condition must change, otherwise it becomes an infinite loop.", 35),
  O("total = 0\nfor i in range(1, 5):\n    total += i\nprint(total)", "10"),
  P("Write a program that prints the numbers 1 to 5 once with a for loop and once with a while loop. Then explain the code line by line.",
    [ck("A for loop using range()", r"for\s+\w+\s+in\s+range\s*\("), ck("A while loop", r"\bwhile\b"),
     ck("The while loop changes its counter", r"\w+\s*\+=\s*1|\w+\s*=\s*\w+\s*\+\s*1"), ck("Prints inside the loops", r"print\s*\(")],
    "for i in range(1, 6):\n    print(i)\n\nn = 1\nwhile n <= 5:\n    print(n)\n    n += 1",
    [pt("Explains range()", r"range"), pt("Explains the while condition or the counter update", r"condition|counter|increment|\+= ?1|increase")],
    "The for loop uses range(1, 6) to produce 1 to 5 and prints each value. The while loop starts n at 1, repeats while n <= 5, prints n and then increases n by 1 so the loop ends.", 20)],
 "functions": [
  E("What is a function? Explain parameters, return values and why functions are useful.",
    [pt("A reusable, named block of code", r"reus", r"named", r"block of code"),
     pt("Parameters (inputs) are passed in", r"parameter", r"argument", r"input"),
     pt("return sends a value back", r"return"),
     pt("Avoids repetition and organises code", r"repeat|repetition|organi|maintain|readab", must=False)],
    "A function is a named, reusable block of code. It can take parameters as inputs and use return to send a result back to the caller. Functions are useful because they avoid repeating code and keep a program organised.", 30),
  O("def add(a, b=10):\n    return a + b\n\nprint(add(5))\nprint(add(5, 1))", "15\n6"),
  D("This function should return the square of a number, but print(square(4)) shows None. Fix it and explain why.",
    "def square(n):\n    n * n\n\nprint(square(4))",
    [ck("Returns the result with return", r"return\s+n\s*(\*\*\s*2|\*\s*n)")],
    "def square(n):\n    return n * n\n\nprint(square(4))",
    [pt("The function never returns the value", r"return"), pt("Without return a function gives None", r"none", must=False)],
    "The function calculates n * n but never returns it, so the caller receives None. Adding return n * n sends the value back.")],
 "lists": [
  E("Explain what a list is, how indexing and slicing work, and name three list methods.",
    [pt("A list is ordered and changeable", r"ordered", r"mutable|changeable|modif"),
     pt("Indexing starts at 0", r"index.*\b0\b", r"zero", r"start.*\b0\b"),
     pt("Slicing returns part of a list", r"slic", r"\[\s*\d*\s*:\s*\d*\s*\]"),
     pt("Methods such as append, remove, sort", r"append", r"insert", r"remove", r"pop", r"sort", r"reverse", r"extend")],
    "A list is an ordered, changeable collection written in square brackets. Indexing starts at 0, so items[0] is the first item and items[-1] is the last. Slicing such as items[1:3] returns part of the list. Useful methods are append, remove and sort.", 30),
  O("nums = [4, 1, 3]\nnums.append(2)\nnums.sort()\nprint(nums)\nprint(nums[-1])", "[1, 2, 3, 4]\n4"),
  P("Write a program that finds the largest number in the list [4, 9, 2, 7] without using max().",
    [ck("Uses a for loop", r"\bfor\b"), ck("Compares values with >", r">"), ck("Does not use max()", r"\bmax\s*\(", must_not=True),
     ck("Prints the result", r"print\s*\(")],
    "numbers = [4, 9, 2, 7]\nlargest = numbers[0]\nfor n in numbers:\n    if n > largest:\n        largest = n\nprint(largest)")],
 "tuples": [
  E("How is a tuple different from a list? When would you use a tuple?",
    [pt("A tuple is immutable (cannot be changed)", r"immutab", r"cannot be (changed|modified)", r"unchangeable"),
     pt("A list is mutable (can be changed)", r"list.*(mutab|chang|modif)", r"(mutab|changeable).*list"),
     pt("Tuples suit fixed data, such as coordinates or dictionary keys", r"fixed", r"constant", r"coordinate", r"dictionary key", r"hashab")],
    "A tuple is immutable, so its items cannot be changed after it is created, while a list is mutable and can be changed. I would use a tuple for fixed data such as coordinates or days of the week, and tuples can also be used as dictionary keys.", 30),
  O("t = (1, 2, 3)\na, b, c = t\nprint(b)\nprint(len((5,)))", "2\n1"),
  D("Fix the code so that single is a tuple, not an int, and explain the fix.",
    "single = (5)\nprint(type(single))",
    [ck("Uses a trailing comma: (5,)", r"\(\s*5\s*,\s*\)")],
    "single = (5,)\nprint(type(single))",
    [pt("The comma makes the tuple", r"comma")],
    "Brackets alone do not make a tuple; the trailing comma does, so (5,) is a tuple while (5) is just the number 5.")],
 "sets": [
  E("Explain what a set is and give two situations where a set is better than a list.",
    [pt("A set holds unique items (no duplicates)", r"unique", r"no duplicate", r"duplicate"),
     pt("A set is unordered (no indexing)", r"unordered", r"no (index|order)", r"not (ordered|indexed)"),
     pt("Good for removing duplicates, fast membership tests or set operations", r"remov\w* duplicate", r"membership", r"fast", r"union", r"intersection", r"common")],
    "A set is an unordered collection of unique items, so duplicates are removed automatically and items cannot be accessed by index. Sets are better than lists for removing duplicates and for fast membership tests, and they support union and intersection.", 30),
  O("a = {1, 2, 3}\nb = {2, 3, 4}\nprint(sorted(a & b))\nprint(len(a | b))", "[2, 3]\n4"),
  P("Remove the duplicates from [3, 1, 3, 2, 1] using a set and print the result in sorted order.",
    [ck("Uses set()", r"set\s*\("), ck("Sorts the result", r"sorted\s*\(|\.sort\s*\("), ck("Prints the result", r"print\s*\(")],
    "items = [3, 1, 3, 2, 1]\nunique = sorted(set(items))\nprint(unique)", qtype="practical")],
 "dictionaries": [
  E("What is a dictionary? Explain keys and values, and how to safely read a key that may not exist.",
    [pt("Stores key-value pairs", r"key.*value", r"pair"),
     pt("Keys are unique and immutable", r"unique", r"immutab", r"hashab"),
     pt("Safe read with get() or the in operator", r"\.get", r"\bget\s*\(", r"\bin\b", r"keyerror", r"default")],
    "A dictionary stores key-value pairs. Each key is unique and must be immutable, and it is used to look up its value. To read a key that may not exist safely, use the get() method with a default value, or check with the in operator, instead of d[key] which raises a KeyError.", 30),
  O('d = {"a": 1, "b": 2}\nd["c"] = 3\nprint(d.get("z", 0))\nprint(len(d))', "0\n3"),
  P("Count how many times each word appears in the sentence 'to be or not to be' and print the dictionary.",
    [ck("Splits the sentence into words", r"\.split\s*\("), ck("Loops over the words", r"\bfor\b"),
     ck("Builds a dictionary", r"\{\s*\}|dict\s*\("), ck("Prints the result", r"print\s*\(")],
    'text = "to be or not to be"\ncounts = {}\nfor word in text.split():\n    counts[word] = counts.get(word, 0) + 1\nprint(counts)', qtype="practical")],
 "strings": [
  E("Explain that strings are immutable and describe three useful string methods with examples.",
    [pt("Strings are immutable", r"immutab", r"cannot be (changed|modified)"),
     pt("Methods such as upper, strip, split, replace", r"upper", r"lower", r"strip", r"split", r"join", r"replace", r"find"),
     pt("Slicing or indexing works on strings", r"slic", r"index", r"\[\s*\d*\s*:\s*\d*\s*\]", must=False)],
    'Strings are immutable, which means a string cannot be changed after it is created; methods return a new string instead. For example, "python".upper() gives "PYTHON", " hi ".strip() removes the spaces, and "a-b".split("-") returns a list. Slicing such as s[1:4] gives part of a string.', 35, True),
  O('s = "python"\nprint(s[1:4])\nprint(s.upper()[0] + s[-1])', "yth\nPn"),
  P("Write a program that asks for a word and prints whether it is a palindrome.",
    [ck("Reads input", r"input\s*\("), ck("Reverses or compares characters", r"\[::-1\]|reversed\s*\(|\bwhile\b|\bfor\b"),
     ck("Compares with ==", r"=="), ck("Prints a result", r"print\s*\(")],
    'word = input("Word: ")\nif word == word[::-1]:\n    print("Palindrome")\nelse:\n    print("Not a palindrome")')],
 "exception handling": [
  E("Explain try, except, else and finally. When does the finally block run?",
    [pt("try holds the risky code", r"\btry\b"),
     pt("except handles the error", r"except"),
     pt("else runs only when there was no error", r"else.*(no (error|exception)|without|not (raised|occur))", r"no (error|exception).*else"),
     pt("finally always runs", r"finally.*(always|every|whether|regardless)", r"(always|regardless).*finally")],
    "The try block contains code that might fail. If an error happens, the matching except block handles it so the program does not crash. The else block runs only when no error occurred, and the finally block always runs, whether or not an error happened, which makes it good for cleanup.", 35),
  O('try:\n    print(10 / 0)\nexcept ZeroDivisionError:\n    print("error")\nfinally:\n    print("done")', "error\ndone"),
  P("Write a program that keeps asking for a whole number until the user types a valid one.",
    [ck("Loops with while", r"\bwhile\b"), ck("Uses try", r"\btry\s*:"), ck("Catches ValueError", r"except\s+ValueError"),
     ck("Converts with int()", r"int\s*\("), ck("Reads input", r"input\s*\(")],
    'while True:\n    try:\n        number = int(input("Number: "))\n        break\n    except ValueError:\n        print("Please enter a whole number.")\nprint("You entered", number)')],
 "file handling": [
  E("Explain the file modes r, w and a, and why the with statement is recommended.",
    [pt("r reads a file", r"\br\b.*read", r"read.*\br\b"),
     pt("w writes and overwrites", r"\bw\b.*(writ|overwrit|erase)", r"overwrit"),
     pt("a appends to the end", r"\ba\b.*append", r"append"),
     pt("with closes the file automatically", r"clos")],
    "Mode r opens a file for reading, w opens it for writing and overwrites any old content, and a appends new content at the end. The with statement is recommended because it closes the file automatically, even if an error happens.", 30),
  O('with open("t.txt", "w") as f:\n    f.write("hi")\nwith open("t.txt") as f:\n    print(f.read())', "hi"),
  X("Explain line by line what this program does.",
    'with open("log.txt", "a") as f:\n    f.write("Day 1 done\\n")\nwith open("log.txt") as f:\n    for line in f:\n        print(line.strip())',
    [pt("Opens log.txt in append mode", r"append", r"mode.{0,6}\ba\b", r"\"a\""),
     pt("with closes the file automatically", r"clos", r"with"),
     pt("Writes a line of text", r"writ"),
     pt("Reads the file line by line", r"line by line", r"each line", r"loop", r"\bfor\b"),
     pt("strip() removes the newline or extra spaces", r"strip", r"newline", r"whitespace|spaces")],
    "The first with block opens log.txt in append mode, so new text is added at the end, and writes the line \"Day 1 done\". The with statement closes the file automatically. The second block opens the file for reading and loops over it line by line, printing each line after strip() removes the newline and extra spaces.", 30)],
 "oop concepts": [
  E("Explain the difference between a class and an object, and describe inheritance with an example.",
    [pt("A class is a blueprint", r"blueprint", r"template", r"design"),
     pt("An object is an instance of the class", r"instance", r"object.*(creat|made|built)"),
     pt("Inheritance: a child class reuses a parent class", r"inherit", r"child", r"parent")],
    "A class is a blueprint that describes data and behaviour, and an object is an instance created from that class. With inheritance a child class reuses a parent class. For example, a Dog class can inherit from an Animal class and reuse its methods.", 35, True),
  O('class A:\n    def hi(self):\n        return "A"\n\nclass B(A):\n    def hi(self):\n        return "B"\n\nprint(A().hi(), B().hi())', "A B"),
  P("Write a class Rectangle with width and height and a method area() that returns the area. Create an object and print its area.",
    [ck("Defines class Rectangle", r"class\s+Rectangle"), ck("Has an __init__ method", r"def\s+__init__"),
     ck("Stores self.width", r"self\.width"), ck("Defines area()", r"def\s+area"), ck("Returns a value", r"\breturn\b"),
     ck("Prints the area", r"print\s*\(")],
    "class Rectangle:\n    def __init__(self, width, height):\n        self.width = width\n        self.height = height\n\n    def area(self):\n        return self.width * self.height\n\nr = Rectangle(4, 5)\nprint(r.area())")],
 "modules and packages": [
  E("What is the difference between a module and a package? Show two ways to import.",
    [pt("A module is a single .py file", r"module.*(file|\.py)"),
     pt("A package is a folder of modules", r"package.*(folder|directory)"),
     pt("Import styles: import x and from x import y", r"\bimport\b")],
    "A module is a single .py file containing reusable code, while a package is a folder of modules, usually with an __init__.py file. You can write import math to use math.sqrt(), or from math import sqrt to use sqrt() directly.", 30),
  O("import math\nfrom math import sqrt\nprint(sqrt(25))\nprint(math.floor(2.7))", "5.0\n2"),
  P("Write a program that imports the random module and prints a random whole number from 1 to 6.",
    [ck("Imports random", r"import\s+random|from\s+random\s+import"), ck("Uses randint()", r"randint\s*\("), ck("Prints the number", r"print\s*\(")],
    "import random\nprint(random.randint(1, 6))")],
 "basic projects": [
  E("Describe how you would plan and build a small number-guessing game before writing code.",
    [pt("Plans the inputs, outputs and steps first", r"plan", r"input", r"output", r"step"),
     pt("Builds it in small parts (loop, function)", r"function", r"loop", r"small", r"part", r"piece", r"increment"),
     pt("Tests and handles invalid input or edge cases", r"test", r"validat", r"edge", r"invalid")],
    "First I would plan the game: the computer picks a secret number, the player enters guesses, and the program says too high, too low or correct. Then I would build it in small parts, such as a loop and a function for checking a guess, and test each part. Finally I would handle invalid input and edge cases such as non-numbers.", 35),
  O('scores = {"a": 3, "b": 5}\nbest = max(scores, key=scores.get)\nprint(best)', "b"),
  D("This loop should print three tries and then stop, but it never ends. Fix it and explain why.",
    'count = 0\nwhile count < 3:\n    print("try", count)',
    [ck("Changes the counter inside the loop", r"count\s*\+=\s*1|count\s*=\s*count\s*\+\s*1")],
    'count = 0\nwhile count < 3:\n    print("try", count)\n    count += 1',
    [pt("The counter never changes, so the loop never ends", r"infinite|never (end|stop)|forever|(does|doesn.?t)\s*(not )?(end|stop)|counter|count.*(change|increase|update)|increment")],
    "count never changes, so count < 3 is always true and the loop runs forever. Adding count += 1 inside the loop makes it stop.")],
}}


def S(prompt, points, terms, words=50, example=True):
    return {"prompt": prompt, "points": points, "terms": terms, "target_words": words, "needs_example": example}


SPOKEN = {"python": {
 "introduction to python": S("Explain what Python is and why many beginners start with it. Give one real-time example of where Python is used.",
    [pt("It is a high-level interpreted language", r"interpret", r"high[- ]level", r"programming language"), pt("It is simple and readable", r"simple", r"easy", r"readab"),
     pt("A real use: web, data, automation or AI", r"\bweb\b", r"\bdata\b", r"automat", r"\bAI\b", r"machine learning")], [r"python", r"programming"]),
 "variables and data types": S("Explain what a variable is in Python and name the main data types. Give one real-time example.",
    [pt("A variable stores or refers to a value", r"stor", r"refer", r"hold", r"name"), pt("Names the types: int, float, string, bool", r"\bint", r"float", r"string|\bstr\b", r"bool")], [r"variable", r"data ?type", r"\bint", r"string", r"float"]),
 "operators": S("Explain the difference between the / and // operators in Python. Give one real-time example.",
    [pt("/ gives a decimal (float) result", r"decimal", r"float", r"true division"), pt("// gives the whole-number (floor) result", r"whole", r"floor", r"integer", r"without (the )?decimal")], [r"operator", r"divi", r"remainder", r"slash"]),
 "conditional statements": S("Explain how an if, elif, else statement works in Python. Give one real-time example.",
    [pt("if runs when a condition is true", r"\bif\b.*(true|condition)", r"condition"), pt("elif checks another condition", r"elif|else if"), pt("else runs otherwise", r"\belse\b|otherwise")], [r"\bif\b", r"\belse\b", r"condition"]),
 "loops": S("Explain how a for loop works in Python. Give one real-time example.",
    [pt("It repeats for each item in a sequence or range", r"each", r"every", r"sequence", r"range", r"iterat", r"repeat"), pt("The loop variable takes each value in turn", r"variable", r"takes", r"one by one", r"each value"), pt("Gives an example", r"example", r"for instance", r"suppose", must=False)], [r"\bfor\b", r"loop", r"range", r"repeat", r"iterat"]),
 "functions": S("Explain what a function is in Python and why we use it. Give one real-time example.",
    [pt("A reusable block of code", r"reus", r"block", r"named"), pt("It can take parameters and return a value", r"parameter", r"argument", r"return", r"input"), pt("Avoids repeating code", r"repeat", r"repetition", r"again and again", r"organi")], [r"function", r"\bdef\b", r"return", r"parameter"]),
 "lists": S("Explain what a list is in Python and how you add or access items. Give one real-time example.",
    [pt("An ordered, changeable collection", r"ordered", r"collection", r"mutable|changeable"), pt("Access with an index starting at zero", r"index", r"zero", r"position"), pt("Add items with append", r"append", r"insert", r"add")], [r"list", r"item", r"index", r"append"]),
 "tuples": S("Explain how a tuple is different from a list. Give one real-time example.",
    [pt("A tuple cannot be changed (immutable)", r"immutab", r"cannot be (changed|modified)", r"can.?t be (changed|modified)", r"unchangeable"), pt("A list can be changed", r"list.*(chang|modif|mutab)", r"(chang|mutab).*list")], [r"tuple", r"list", r"immutable", r"bracket"]),
 "sets": S("Explain what a set is and when you would use it. Give one real-time example.",
    [pt("A set has only unique items", r"unique", r"duplicate"), pt("A set has no fixed order or index", r"unordered", r"no order", r"no index", r"not ordered"), pt("Used for removing duplicates or fast lookups", r"remov\w* duplicate", r"lookup", r"membership", r"fast", r"union", r"common")], [r"\bset\b", r"unique", r"duplicate"]),
 "dictionaries": S("Explain what a dictionary is in Python. Give one real-time example.",
    [pt("It stores key and value pairs", r"key.*value", r"pair"), pt("You look up a value using its key", r"look ?up", r"access", r"find", r"get")], [r"dictionary", r"\bkey", r"value"]),
 "strings": S("Explain what a string is in Python and name two string methods. Give one real-time example.",
    [pt("A string is text, a sequence of characters", r"text", r"characters?", r"sequence"), pt("Names string methods like upper, lower, split, strip", r"upper", r"lower", r"split", r"strip", r"replace", r"join")], [r"string", r"text", r"method", r"upper", r"lower"]),
 "exception handling": S("Explain how try and except are used for exception handling in Python. Give one real-time example.",
    [pt("try holds code that may fail", r"\btry\b", r"may fail", r"risky"), pt("except handles the error so the program continues", r"except", r"handle", r"catch", r"crash")], [r"\btry\b", r"except", r"error", r"exception"]),
 "file handling": S("Explain how to read and write a file in Python. Give one real-time example.",
    [pt("Use open() with a mode", r"open", r"mode"), pt("Use read or write", r"read", r"write"), pt("Use with so the file closes automatically", r"\bwith\b", r"clos")], [r"file", r"open", r"read", r"write"]),
 "oop concepts": S("Explain the idea of a class and an object in Python. Give one real-time example.",
    [pt("A class is a blueprint", r"blueprint", r"template", r"design"), pt("An object is created from the class", r"object", r"instance")], [r"class", r"object", r"method", r"attribute"]),
 "modules and packages": S("Explain what a module is in Python and how you import it. Give one real-time example.",
    [pt("A module is a file of reusable code", r"file", r"reus", r"\.py"), pt("You use the import statement", r"\bimport\b")], [r"module", r"import", r"package"]),
 "basic projects": S("Describe one small Python project you could build and how you would plan it.",
    [pt("Describes what the project does", r"project", r"build", r"app", r"program", r"game"), pt("Plans steps or inputs and outputs", r"plan", r"step", r"input", r"output", r"first"), pt("Mentions testing", r"test", r"check", r"improve", must=False)], [r"project", r"plan", r"build"], 60, False),
}}


def written_questions(tech_name, topic_name):
    return WRITTEN.get(tech_name.lower(), {}).get(topic_name.lower())


def spoken_question(tech_name, topic_name):
    return SPOKEN.get(tech_name.lower(), {}).get(topic_name.lower())
