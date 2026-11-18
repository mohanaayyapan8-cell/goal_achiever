# Database design (planned; models are created phase by phase)

Every user-owned table has a `user` foreign key. "1—*" means one-to-many.

## Relationships
```
User 1—1 UserProfile                      (timezone, reminder time, theme)
User 1—* Domain 1—* Technology 1—* Topic  (Domain/Technology/Topic are user-owned,
                                           seeded with defaults, fully editable)
Topic 1—* LearningContent                 (10 sections: intro, definition, ... revision)
Topic 1—1 LearningProgress (per user)     (status, completed_at)
User 1—* DailyPlan (Day 1..40)  1—* DailyGoal ──> Topic (optional)
                                          DailyGoal: estimated_minutes, status,
                                          rescheduled_from (keeps history)
Topic 1—* WrittenAssessment 1—* WrittenAnswer   (score + rubric feedback per answer)
Topic 1—* SpeakingAssessment 1—* SpeakingAnswer (transcript, edited transcript, rubric)
AptitudeQuestion (shared bank) ; User 1—* AptitudeAttempt (score, time taken, answers)
CodingProblem (shared bank) ; User 1—* CodingSubmission (code, status, manual/auto)
User 1—* StreakRecord (one row per calendar date: completed? streak_count)
User 1—* Achievement ; User 1—* Notification
User 1—* Resume (structured fields + optional private upload)
User 1—* StudySession (start, minutes) -> total learning hours
```

## Constraints and indexes planned
- `StreakRecord`: unique (user, date) -> prevents duplicate streak increments.
- `DailyPlan`: unique (user, day_number); `DailyGoal` index (plan, status).
- `LearningProgress`: unique (user, topic).
- `AptitudeAttempt`, `CodingSubmission`, `WrittenAnswer`: index (user, created_at).
- `Domain`: unique (user, name); `Technology`: unique (domain, name); `Topic`: unique (technology, name).
- Deleting a domain cascades to its technologies/topics, but streak records,
  achievements and past assessment history are never deleted by streak resets.

## Shared vs private data
- **Shared (admin-managed)**: AptitudeQuestion, CodingProblem, default content.
- **Private (per user)**: everything else.
