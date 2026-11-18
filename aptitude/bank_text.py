"""Hand-written aptitude questions (original). Q(...) options are shuffled once with a fixed seed;
W(...) keeps the given option order (used when the order is part of the question)."""


def Q(topic, stem, correct, wrongs, explanation, passage=""):
    return {"topic": topic, "stem": stem, "correct_text": correct, "wrongs": wrongs, "explanation": explanation, "passage": passage, "fixed": False}


def W(topic, stem, options, answer_index, explanation):
    return {"topic": topic, "stem": stem, "options": options, "correct": answer_index, "explanation": explanation, "passage": "", "fixed": True}


SYL = ["Only I follows", "Only II follows", "Both I and II follow", "Neither I nor II follows"]
PART = ["Part A", "Part B", "Part C", "Part D"]

LOGICAL = [
 # ---- Blood relations
 Q("Blood Relations", "Pointing to a man, Rita said, 'He is the son of my mother's only brother.' How is the man related to Rita?", "Cousin", ["Brother", "Uncle", "Nephew"], "Rita's mother's brother is Rita's maternal uncle. His son is Rita's cousin."),
 Q("Blood Relations", "A is the brother of B. B is the sister of C. C is the father of D. How is A related to D?", "Uncle", ["Father", "Brother", "Grandfather"], "A and C are siblings (both are siblings of B). C is D's father, so A is D's uncle."),
 Q("Blood Relations", "If P is the mother of Q and Q is the sister of R, how is P related to R?", "Mother", ["Aunt", "Sister", "Grandmother"], "Q and R are siblings, so P, the mother of Q, is also the mother of R."),
 Q("Blood Relations", "Introducing a woman, Ravi said, 'Her mother is the only daughter of my mother.' How is the woman related to Ravi?", "Niece", ["Sister", "Cousin", "Daughter"], "The only daughter of Ravi's mother is Ravi's sister. The woman's mother is Ravi's sister, so the woman is Ravi's niece."),
 Q("Blood Relations", "A's father is B's son. How is A related to B?", "Grandchild", ["Son", "Nephew", "Father"], "B's son is A's father, so B is A's grandparent and A is B's grandchild."),
 Q("Blood Relations", "Pointing to a photograph, a man said, 'I have no brother or sister, but that man's father is my father's son.' Whose photograph was it?", "His son's", ["His own", "His father's", "His nephew's"], "With no siblings, 'my father's son' is the speaker himself. So the man in the photo's father is the speaker, making the photo the speaker's son."),
 # ---- Seating arrangements
 Q("Seating Arrangements", "Five friends A, B, C, D and E sit in a row facing north. A is at the extreme left, B sits next to A, and C is at the extreme right. D does not sit next to C. Who sits in the middle?", "D", ["B", "E", "A"], "Order so far: A, B, _, _, C. D cannot be next to C, so D takes seat 3 and E seat 4. The middle seat belongs to D."),
 W("Seating Arrangements", "Four people P, Q, R and S sit around a circular table facing the centre. P sits opposite R. Q sits immediately to the left of P. Who sits opposite Q?", ["R", "S", "P", "Cannot be determined"], 1, "Facing the centre, a person's left is the next seat clockwise. Going clockwise: P, Q, R, S. Q's opposite seat is S."),
 Q("Seating Arrangements", "In a row of 6 people, Mina is 3rd from the left and Joel is 2nd from the right. How many people sit between them?", "1", ["0", "2", "3"], "Joel is 2nd from the right, which is 5th from the left. Mina is 3rd, so only the 4th person is between them."),
 Q("Seating Arrangements", "Eight people sit in a row. Kiran is 3rd from the left and Lata is 4th from the right. How many people sit between them?", "1", ["0", "2", "3"], "Lata is 4th from the right, which is 5th from the left (8 − 4 + 1). Kiran is 3rd, so only the 4th person is between them."),
 Q("Seating Arrangements", "Five students sit in a row. Tara is to the right of Uma but to the left of Vik. Wes is to the right of Vik. Xia is to the left of Uma. Who sits at the extreme right?", "Wes", ["Vik", "Tara", "Xia"], "Left to right the order is Xia, Uma, Tara, Vik, Wes."),
 # ---- Syllogisms
 W("Syllogisms", "Statements: All pens are books. All books are tables.\nConclusions: I. All pens are tables. II. All tables are pens.", SYL, 0, "Pens ⊂ books ⊂ tables, so all pens are tables (I). The reverse (II) does not follow."),
 W("Syllogisms", "Statements: Some cats are dogs. All dogs are birds.\nConclusions: I. Some cats are birds. II. All birds are dogs.", SYL, 0, "The cats that are dogs are birds too, so some cats are birds (I). Nothing says every bird is a dog (II)."),
 W("Syllogisms", "Statements: No fruit is a stone. Some stones are rocks.\nConclusions: I. Some rocks are not fruits. II. No rock is a fruit.", SYL, 0, "The rocks that are stones cannot be fruits, so some rocks are not fruits (I). Other rocks might still be fruits, so II does not follow."),
 W("Syllogisms", "Statements: All doctors are readers. Some readers are singers.\nConclusions: I. Some doctors are singers. II. Some singers are readers.", SYL, 1, "'Some readers are singers' reverses to 'some singers are readers' (II). The doctors and singers may not overlap, so I does not follow."),
 W("Syllogisms", "Statements: Some A are B. Some B are C.\nConclusions: I. Some A are C. II. Some C are B.", SYL, 1, "'Some B are C' reverses to 'some C are B' (II). Two 'some' statements do not link A and C, so I does not follow."),
 # ---- Puzzles
 Q("Puzzles", "Today is Wednesday. What day of the week will it be after 45 days?", "Saturday", ["Friday", "Sunday", "Monday"], "45 = 6 weeks + 3 days. Three days after Wednesday is Saturday."),
 Q("Puzzles", "A father is three times as old as his son. After 12 years he will be twice as old as his son. What is the son's present age?", "12 years", ["10 years", "14 years", "16 years"], "Let the son be x: 3x + 12 = 2(x + 12), so x = 12."),
 Q("Puzzles", "What is the angle between the hour hand and the minute hand of a clock at 3:15?", "7.5°", ["0°", "15°", "30°"], "At 3:15 the minute hand is at 90°. The hour hand has moved a quarter of the way from 3 to 4: 90° + 7.5° = 97.5°. Difference = 7.5°."),
 Q("Puzzles", "A farmer has 17 sheep. All but 9 of them run away. How many sheep are left?", "9", ["8", "17", "0"], "'All but 9' means 9 stayed."),
 Q("Puzzles", "If 5 machines make 5 widgets in 5 minutes, how many minutes do 100 machines need to make 100 widgets?", "5 minutes", ["1 minute", "20 minutes", "100 minutes"], "Each machine makes one widget in 5 minutes, so 100 machines make 100 widgets in 5 minutes."),
 # ---- Analogies
 Q("Analogies", "Book : Reading :: Fork : ?", "Eating", ["Cooking", "Washing", "Cutting"], "A book is used for reading; a fork is used for eating."),
 Q("Analogies", "Doctor : Hospital :: Teacher : ?", "School", ["Market", "Court", "Factory"], "A doctor works in a hospital; a teacher works in a school."),
 Q("Analogies", "Bird : Nest :: Bee : ?", "Hive", ["Cave", "Burrow", "Web"], "A bird lives in a nest; a bee lives in a hive."),
 Q("Analogies", "Fish : Swim :: Bird : ?", "Fly", ["Walk", "Crawl", "Run"], "Fish move by swimming; birds move by flying."),
 Q("Analogies", "Hot : Cold :: Up : ?", "Down", ["High", "Over", "Top"], "Hot and cold are opposites; the opposite of up is down."),
 Q("Analogies", "Pen : Write :: Knife : ?", "Cut", ["Draw", "Paint", "Read"], "A pen is used to write; a knife is used to cut."),
 Q("Analogies", "Ink : Pen :: Petrol : ?", "Engine", ["Road", "Driver", "Wheel"], "Ink powers a pen as petrol powers an engine."),
]

VERBAL = [
 # ---- Grammar
 Q("Grammar", "Which sentence about not knowing an answer is correct?", "She doesn't know the answer.", ["She don't know the answer.", "She not know the answer.", "She doesn't knows the answer."], "With 'she', use 'doesn't' followed by the base verb 'know'."),
 Q("Grammar", "Fill in the blank: Neither of the boys ___ present.", "was", ["were", "are", "be"], "'Neither' takes a singular verb, so 'was'."),
 Q("Grammar", "Fill in the blank: I have ___ my homework already.", "finished", ["finish", "finishing", "finishes"], "The present perfect uses 'have' + past participle: 'have finished'."),
 Q("Grammar", "Which sentence about children playing is correct?", "The children are playing in the garden.", ["The children is playing in the garden.", "The childrens are playing in the garden.", "The children playing in the garden."], "'Children' is already plural, so it takes 'are' and has no extra 's'."),
 Q("Grammar", "Fill in the blank: If I ___ you, I would apologise.", "were", ["was", "am", "be"], "Unreal conditions use 'were' for every subject: 'If I were you'."),
 Q("Grammar", "Which sentence is grammatically correct?", "He has lived here since 2015.", ["He lives here since 2015.", "He is living here since 2015.", "He live here since 2015."], "'Since' with a starting point in the past needs the present perfect: 'has lived'."),
 # ---- Tenses
 Q("Tenses", "She ___ to school every day.", "goes", ["go", "going", "gone"], "A daily habit uses the simple present; with 'she' the verb takes -es: 'goes'."),
 Q("Tenses", "By the time we arrived, the film ___.", "had started", ["has started", "starts", "was start"], "An action finished before another past action uses the past perfect: 'had started'."),
 Q("Tenses", "I ___ TV when the phone rang.", "was watching", ["watched", "am watching", "have watched"], "A longer action in progress in the past, interrupted by another, uses the past continuous."),
 Q("Tenses", "They ___ in Chennai since 2016.", "have lived", ["live", "lived", "are living"], "'Since 2016' signals the present perfect: 'have lived'."),
 Q("Tenses", "Tomorrow at this time, I ___ on the beach.", "will be lying", ["lie", "lay", "have lain"], "An action in progress at a future moment uses the future continuous: 'will be lying'."),
 Q("Tenses", "He said that he ___ the report the day before.", "had finished", ["has finished", "finishes", "will finish"], "In reported speech the earlier action moves back to the past perfect: 'had finished'."),
 # ---- Articles
 Q("Articles", "She is ___ honest girl.", "an", ["a", "the", "some"], "'Honest' starts with a vowel sound (the h is silent), so 'an'."),
 Q("Articles", "He plays ___ guitar very well.", "the", ["a", "an", "some"], "Musical instruments are usually used with 'the': 'plays the guitar'."),
 Q("Articles", "___ sun rises in the east.", "The", ["A", "An", "Some"], "There is only one sun, so we use 'The'."),
 Q("Articles", "He is ___ European.", "a", ["an", "the", "some"], "'European' begins with a 'yoo' sound (a consonant sound), so 'a'."),
 Q("Articles", "I saw ___ one-eyed man.", "a", ["an", "the", "some"], "'One' begins with a 'w' sound (a consonant sound), so 'a'."),
 Q("Articles", "She wants to become ___ engineer.", "an", ["a", "the", "some"], "'Engineer' begins with a vowel sound, so 'an'."),
 # ---- Prepositions
 Q("Prepositions", "The book is ___ the table.", "on", ["in", "of", "to"], "Something resting on a surface is 'on' it."),
 Q("Prepositions", "She is good ___ mathematics.", "at", ["with", "for", "on"], "The standard phrase is 'good at' a subject or skill."),
 Q("Prepositions", "He has been waiting ___ 9 o'clock.", "since", ["for", "from", "by"], "'Since' is used with a point in time (9 o'clock); 'for' is used with a length of time."),
 Q("Prepositions", "The meeting is ___ Monday.", "on", ["at", "in", "by"], "Days of the week take 'on'."),
 Q("Prepositions", "She is afraid ___ spiders.", "of", ["from", "with", "for"], "'Afraid of' is the correct phrase."),
 Q("Prepositions", "He apologised ___ being late.", "for", ["to", "at", "on"], "We apologise 'for' something."),
 # ---- Subject-verb agreement
 Q("Subject-Verb Agreement", "Each of the students ___ a laptop.", "has", ["have", "are having", "having"], "'Each' is singular, so the verb is 'has'."),
 Q("Subject-Verb Agreement", "Neither the teacher nor the students ___ ready.", "are", ["is", "was", "has been"], "With 'neither...nor' the verb agrees with the nearer subject, 'students', so 'are'."),
 Q("Subject-Verb Agreement", "The news ___ surprising.", "is", ["are", "were", "have been"], "'News' is an uncountable noun and takes a singular verb."),
 Q("Subject-Verb Agreement", "Bread and butter ___ my favourite breakfast.", "is", ["are", "were", "have been"], "Two items that form one single idea take a singular verb."),
 Q("Subject-Verb Agreement", "A number of students ___ absent today.", "are", ["is", "was", "has been"], "'A number of' means 'several', so the plural verb 'are' is used."),
 Q("Subject-Verb Agreement", "Mathematics ___ my favourite subject.", "is", ["are", "were", "have been"], "Names of subjects ending in -ics are singular."),
 # ---- Synonyms
 Q("Synonyms", "Choose the word closest in meaning to ABUNDANT.", "Plentiful", ["Scarce", "Tiny", "Rare"], "Abundant means available in large quantity, like plentiful."),
 Q("Synonyms", "Choose the word closest in meaning to BRIEF.", "Short", ["Long", "Wide", "Heavy"], "Brief means lasting a short time."),
 Q("Synonyms", "Choose the word closest in meaning to CONCEAL.", "Hide", ["Reveal", "Find", "Show"], "To conceal is to hide."),
 Q("Synonyms", "Choose the word closest in meaning to DILIGENT.", "Hardworking", ["Lazy", "Careless", "Clever"], "Diligent means careful and hardworking."),
 Q("Synonyms", "Choose the word closest in meaning to EXPAND.", "Enlarge", ["Shrink", "Reduce", "Cancel"], "To expand is to become or make larger."),
 Q("Synonyms", "Choose the word closest in meaning to GENUINE.", "Authentic", ["Fake", "Cheap", "Rare"], "Genuine means real, or authentic."),
 # ---- Antonyms
 Q("Antonyms", "Choose the word opposite in meaning to ANCIENT.", "Modern", ["Old", "Historic", "Antique"], "Ancient means very old; the opposite is modern."),
 Q("Antonyms", "Choose the word opposite in meaning to VICTORY.", "Defeat", ["Triumph", "Success", "Win"], "The opposite of victory is defeat."),
 Q("Antonyms", "Choose the word opposite in meaning to GENEROUS.", "Stingy", ["Kind", "Giving", "Noble"], "A generous person gives freely; a stingy person does not."),
 Q("Antonyms", "Choose the word opposite in meaning to TRANSPARENT.", "Opaque", ["Clear", "Thin", "Bright"], "Transparent lets light through; opaque does not."),
 Q("Antonyms", "Choose the word opposite in meaning to EXPAND.", "Contract", ["Grow", "Spread", "Stretch"], "To contract is to become smaller, the opposite of expand."),
 Q("Antonyms", "Choose the word opposite in meaning to ACCEPT.", "Reject", ["Take", "Receive", "Agree"], "To reject is to refuse, the opposite of accept."),
 # ---- Sentence correction
 Q("Sentence Correction", "Which option corrects the sentence: 'He go to school daily.'?", "He goes to school daily.", ["He going to school daily.", "He gone to school daily.", "He go to schools daily."], "With 'he' the simple present verb needs -es: 'goes'."),
 Q("Sentence Correction", "Which option corrects the sentence: 'She don't like coffee.'?", "She doesn't like coffee.", ["She not like coffee.", "She didn't likes coffee.", "She don't likes coffee."], "Use 'doesn't' with 'she', followed by the base verb."),
 Q("Sentence Correction", "Which option corrects the sentence: 'I am knowing the answer.'?", "I know the answer.", ["I am known the answer.", "I do knowing the answer.", "I knowing the answer."], "'Know' is a state verb and is not used in the continuous form."),
 Q("Sentence Correction", "Which option corrects the sentence: 'He is more taller than his brother.'?", "He is taller than his brother.", ["He is most taller than his brother.", "He is tallest than his brother.", "He is more tall than his brother."], "'Taller' is already a comparative, so 'more' is not needed."),
 Q("Sentence Correction", "Which option corrects the sentence: 'The informations are useful.'?", "The information is useful.", ["The informations is useful.", "The information are useful.", "The informations were useful."], "'Information' is uncountable: no plural, singular verb."),
 Q("Sentence Correction", "Which option corrects the sentence: 'Me and my friend went to the market.'?", "My friend and I went to the market.", ["Me and my friend goes to the market.", "My friend and me went to the market.", "I and my friend goes to the market."], "'I' is the subject form, and it is polite to name the other person first."),
 # ---- Error detection
 W("Error Detection", "Find the part with the error.\n(A) Each of the girls (B) have completed (C) her assignment (D) on time.", PART, 1, "'Each' is singular, so it should be 'has completed'."),
 W("Error Detection", "Find the part with the error.\n(A) He did not (B) went to (C) the market (D) yesterday.", PART, 1, "After 'did not' the verb stays in its base form: 'go to'."),
 W("Error Detection", "Find the part with the error.\n(A) The teacher (B) gave us (C) a advice (D) about exams.", PART, 2, "'Advice' is uncountable and cannot take 'a'. Say 'some advice'."),
 W("Error Detection", "Find the part with the error.\n(A) She is (B) senior than (C) me (D) by two years.", PART, 1, "'Senior' is followed by 'to', not 'than': 'senior to me'."),
 W("Error Detection", "Find the part with the error.\n(A) Neither of the two (B) answers (C) are (D) correct.", PART, 2, "'Neither' takes a singular verb: 'is correct'."),
 W("Error Detection", "Find the part with the error.\n(A) I have (B) been knowing him (C) for (D) ten years.", PART, 1, "'Know' is a state verb and is not used in a continuous tense: 'have known him'."),
 # ---- Reading comprehension
 Q("Reading Comprehension", "According to the passage, what does the brain do during sleep?", "It clears waste and stores memories", ["It stops working completely", "It forgets what was studied", "It grows larger"], "The passage says the brain clears waste, stores memories and prepares for the next day.",
   "Sleep is not a luxury; it is a biological need. During sleep the brain clears waste, stores memories and prepares for the next day. Students who sleep fewer than six hours often struggle to concentrate and remember what they have studied. Experts therefore advise teenagers to sleep eight to ten hours each night and to keep a regular bedtime."),
 Q("Reading Comprehension", "What happens to students who sleep fewer than six hours?", "They find it hard to concentrate and remember", ["They study faster", "They need no more rest", "They become taller"], "The passage says they 'struggle to concentrate and remember what they have studied'.",
   "Sleep is not a luxury; it is a biological need. During sleep the brain clears waste, stores memories and prepares for the next day. Students who sleep fewer than six hours often struggle to concentrate and remember what they have studied. Experts therefore advise teenagers to sleep eight to ten hours each night and to keep a regular bedtime."),
 Q("Reading Comprehension", "What is the main idea of the passage?", "Sleep is essential for learning and health", ["Teenagers should study at night", "Sleep is a luxury for adults", "Memories are stored only while awake"], "The whole passage explains why sleep is needed and how much teenagers should get.",
   "Sleep is not a luxury; it is a biological need. During sleep the brain clears waste, stores memories and prepares for the next day. Students who sleep fewer than six hours often struggle to concentrate and remember what they have studied. Experts therefore advise teenagers to sleep eight to ten hours each night and to keep a regular bedtime."),
 Q("Reading Comprehension", "What does the passage say libraries offer besides books?", "Computers, online courses and reading clubs", ["Free meals and hotel rooms", "Only newspapers", "Sports training"], "The passage lists computers, online courses and reading clubs.",
   "A library is more than a room full of books. It is a quiet place where people can think, learn and explore new ideas for free. Many libraries now also offer computers, online courses and reading clubs. As a result, they help people of all ages, including those who cannot afford books or internet access."),
 Q("Reading Comprehension", "Who benefits especially from libraries, according to the passage?", "People who cannot afford books or internet access", ["Only school teachers", "Only wealthy readers", "Only young children"], "The passage names people who cannot afford books or internet access.",
   "A library is more than a room full of books. It is a quiet place where people can think, learn and explore new ideas for free. Many libraries now also offer computers, online courses and reading clubs. As a result, they help people of all ages, including those who cannot afford books or internet access."),
 Q("Reading Comprehension", "The word 'explore' in the passage is closest in meaning to:", "Investigate", ["Ignore", "Avoid", "Forget"], "To explore new ideas is to investigate them.",
   "A library is more than a room full of books. It is a quiet place where people can think, learn and explore new ideas for free. Many libraries now also offer computers, online courses and reading clubs. As a result, they help people of all ages, including those who cannot afford books or internet access."),
]

SECTION_OF = {"Blood Relations": "logical", "Seating Arrangements": "logical", "Syllogisms": "logical", "Puzzles": "logical", "Analogies": "logical"}
