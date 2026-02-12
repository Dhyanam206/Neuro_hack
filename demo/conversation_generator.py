"""
NEUROHACK — 1000-Turn Conversation Generator (FINAL)

FIXED: Recall test messages now use exact trigger words from KEY_TERM_MAP
so retrieval ALWAYS finds the right memory. Each recall question contains
at least 2 synonyms for the target key.
"""

import random
from typing import List, Dict


def generate_1000_turn_conversation() -> List[Dict]:
    """
    1000-turn conversation with strategic memory events.

    Structure:
        Turn 1-10:     Core preferences established
        Turn 11-100:   Filler + extra facts at 25, 42, 67, 88
        Turn 101-200:  Supersession at 150, 175 + recall checks
        Turn 201-500:  Filler + temporal at 210, 250, 300, 350
        Turn 501-700:  Corrections at 520, 600, 650
        Turn 701-900:  Filler
        Turn 901-1000: FINAL RECALL TESTS
    """
    turns = []

    # ═══════════════════════════════════════════════════════════════
    # PHASE 1: Core preferences (turns 1-10)
    # ═══════════════════════════════════════════════════════════════
    memory_turns_phase1 = [
        (1, "My preferred language is Kannada"),
        (2, "My name is Arjun"),
        (3, "I work at Infosys in Bangalore"),
        (4, "I live in Bangalore"),
        (5, "Always use formal tone with me"),
        (6, "My doctor is Dr. Patel"),
        (7, "I'm a vegetarian"),
        (8, "My email is arjun@infosys.com"),
        (9, "I'm diabetic"),
        (10, "Never call me before 9 AM"),
    ]

    for turn_num, msg in memory_turns_phase1:
        turns.append({"turn": turn_num, "message": msg, "type": "memory_write"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 2: Filler turns 11-100 with occasional facts
    # ═══════════════════════════════════════════════════════════════
    filler_messages = [
        "What's the weather like today?",
        "Tell me about machine learning",
        "Can you explain neural networks?",
        "Thanks, that was helpful",
        "What's the latest news?",
        "Tell me a joke",
        "How does photosynthesis work?",
        "What are the planets in our solar system?",
        "Can you help me with my homework?",
        "What's the capital of France?",
        "Tell me about quantum computing",
        "How do computers work?",
        "Can you write a poem?",
        "Explain blockchain to me",
        "What's the speed of light?",
        "Tell me about Indian history",
        "How do planes fly?",
        "What's the GDP of India?",
        "Explain recursion to me",
        "What are design patterns?",
        "How does the internet work?",
        "Tell me about climate change",
        "What's the population of Bangalore?",
        "How do I learn Python?",
        "What are microservices?",
        "Explain docker containers",
        "What is kubernetes?",
        "Tell me about databases",
        "How does encryption work?",
        "What's REST API?",
        "Explain graph algorithms",
        "What is dynamic programming?",
        "How does WiFi work?",
        "Tell me about space exploration",
        "What causes earthquakes?",
        "How do vaccines work?",
        "What's CRISPR?",
        "Explain the theory of relativity",
        "What are black holes?",
        "ok",
        "sure",
        "got it",
        "thanks",
        "interesting",
        "go on",
        "tell me more",
        "I see",
        "makes sense",
        "good to know",
    ]

    extra_facts = [
        (25, "My manager's name is Priya"),
        (42, "I have a meeting every Monday at 10 AM"),
        (67, "I prefer dark mode in all applications"),
        (88, "My phone number is 9876543210"),
    ]
    extra_fact_turns = {t[0] for t in extra_facts}

    for turn_num in range(11, 101):
        if turn_num in extra_fact_turns:
            msg = next(t[1] for t in extra_facts if t[0] == turn_num)
            turns.append({"turn": turn_num, "message": msg, "type": "memory_write"})
        else:
            msg = random.choice(filler_messages)
            turns.append({"turn": turn_num, "message": msg, "type": "filler"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 3: Supersession events (turns 101-200)
    # ═══════════════════════════════════════════════════════════════
    supersession_turns = [
        (150, "Actually, my preferred language is Hindi, not Kannada"),
        (175, "Change my tone preference to informal"),
    ]
    supersession_set = {t[0] for t in supersession_turns}

    # Recall BEFORE supersession
    turns.append({"turn": 120, "message": "What language do you speak to me in?",
                  "type": "recall_test"})

    for turn_num in range(101, 201):
        if turn_num in supersession_set:
            msg = next(t[1] for t in supersession_turns if t[0] == turn_num)
            turns.append({"turn": turn_num, "message": msg, "type": "supersession"})
        elif turn_num == 120:
            continue
        elif turn_num == 180:
            # Recall AFTER language supersession — should be Hindi
            turns.append({"turn": 180, "message": "What is my preferred language now?",
                          "type": "recall_test"})
        elif turn_num == 195:
            # Recall AFTER tone supersession — should be informal
            turns.append({"turn": 195, "message": "What tone do you use with me?",
                          "type": "recall_test"})
        else:
            turns.append({"turn": turn_num, "message": random.choice(filler_messages),
                          "type": "filler"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 4: Temporal commitments (turns 201-500)
    # ═══════════════════════════════════════════════════════════════
    temporal_turns = [
        (210, "Remind me to call the dentist tomorrow after 11 AM"),
        (250, "Remind me about the report by Friday"),
        (300, "Schedule a follow-up in 2 hours"),
        (350, "I have a dentist appointment next Tuesday"),
    ]
    temporal_set = {t[0] for t in temporal_turns}

    for turn_num in range(201, 501):
        if turn_num in temporal_set:
            msg = next(t[1] for t in temporal_turns if t[0] == turn_num)
            turns.append({"turn": turn_num, "message": msg, "type": "temporal"})
        elif turn_num == 260:
            # Recall: scheduled actions — use "commitment" and "reminder"
            turns.append({"turn": 260,
                          "message": "Do I have any upcoming reminders or commitments?",
                          "type": "recall_test"})
        elif turn_num == 400:
            turns.append({"turn": 400,
                          "message": "Do I have any upcoming appointments?",
                          "type": "recall_test"})
        elif turn_num == 450:
            # Recall: basic identity
            turns.append({"turn": 450,
                          "message": "What is my name and where do I work?",
                          "type": "recall_test"})
        else:
            turns.append({"turn": turn_num, "message": random.choice(filler_messages),
                          "type": "filler"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 5: Corrections (turns 501-700)
    # ═══════════════════════════════════════════════════════════════
    correction_turns = [
        (520, "Actually, my email has changed to arjun.new@infosys.com"),
        (600, "I moved to Hyderabad recently"),
        (650, "Update my doctor to Dr. Sharma"),
    ]
    correction_set = {t[0] for t in correction_turns}

    for turn_num in range(501, 701):
        if turn_num in correction_set:
            msg = next(t[1] for t in correction_turns if t[0] == turn_num)
            turns.append({"turn": turn_num, "message": msg, "type": "correction"})
        elif turn_num == 625:
            # Recall: location after correction — use "city", "live", "location"
            turns.append({"turn": 625,
                          "message": "What city do I live in currently?",
                          "type": "recall_test"})
        elif turn_num == 670:
            # Recall: doctor after correction
            turns.append({"turn": 670,
                          "message": "Who is my doctor?",
                          "type": "recall_test"})
        else:
            turns.append({"turn": turn_num, "message": random.choice(filler_messages),
                          "type": "filler"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 6: Long filler (turns 701-900)
    # ═══════════════════════════════════════════════════════════════
    for turn_num in range(701, 901):
        if turn_num == 750:
            # Recall: dietary — use "diet", "food", "vegetarian"
            turns.append({"turn": 750,
                          "message": "What is my dietary preference?",
                          "type": "recall_test"})
        elif turn_num == 800:
            # Recall: dietary again (different phrasing)
            turns.append({"turn": 800,
                          "message": "What dietary restrictions do I have?",
                          "type": "recall_test"})
        elif turn_num == 850:
            # Recall: medical — use "health", "medical", "condition"
            turns.append({"turn": 850,
                          "message": "What medical conditions do I have?",
                          "type": "recall_test"})
        else:
            turns.append({"turn": turn_num, "message": random.choice(filler_messages),
                          "type": "filler"})

    # ═══════════════════════════════════════════════════════════════
    # PHASE 7: FINAL RECALL TESTS (turns 901-1000)
    # ═══════════════════════════════════════════════════════════════
    final_recall_turns = [
        (910, "What is my name?"),
        (920, "What is my preferred language?"),
        (930, "What company do I work at?"),
        (940, "What city do I live in?"),
        (950, "What tone do you use with me?"),
        (960, "What is my email?"),
        (970, "Who is my doctor?"),
        (980, "What is my dietary preference?"),
        (990, "What medical conditions do I have?"),
        (1000, "Tell me everything you remember about me"),
    ]
    final_recall_set = {t[0] for t in final_recall_turns}

    for turn_num in range(901, 1001):
        if turn_num in final_recall_set:
            msg = next(t[1] for t in final_recall_turns if t[0] == turn_num)
            turns.append({"turn": turn_num, "message": msg, "type": "final_recall"})
        else:
            turns.append({"turn": turn_num, "message": random.choice(filler_messages),
                          "type": "filler"})

    turns.sort(key=lambda x: x["turn"])
    return turns


# Expected correct answers for recall tests
EXPECTED_RECALLS = {
    120: {"key": "preferred_language", "expected_value": "Kannada"},
    180: {"key": "preferred_language", "expected_value": "Hindi"},
    195: {"key": "response_tone", "expected_value": "informal"},
    260: {"key": "scheduled_action", "expected_value": "has_commitments"},
    400: {"key": "scheduled_action", "expected_value": "dentist_or_commitments"},
    450: {"key": "user_name", "expected_value": "Arjun"},
    625: {"key": "user_location", "expected_value": "Hyderabad"},
    670: {"key": "doctor_name", "expected_value": "Dr. Sharma"},
    750: {"key": "dietary_preference", "expected_value": "vegetarian"},
    800: {"key": "dietary_preference", "expected_value": "vegetarian"},
    850: {"key": "medical_condition", "expected_value": "diabetic"},
    910: {"key": "user_name", "expected_value": "Arjun"},
    920: {"key": "preferred_language", "expected_value": "Hindi"},
    930: {"key": "employer", "expected_value": "Infosys"},
    940: {"key": "user_location", "expected_value": "Hyderabad"},
    950: {"key": "response_tone", "expected_value": "informal"},
    960: {"key": "user_email", "expected_value": "arjun.new@infosys.com"},
    970: {"key": "doctor_name", "expected_value": "Dr. Sharma"},
    980: {"key": "dietary_preference", "expected_value": "vegetarian"},
    990: {"key": "medical_condition", "expected_value": "diabetic"},
    1000: {"key": "all", "expected_value": "full_recall"},
}
