# Grading & Plagiarism Detection - Explained

This document explains how the automated grading and plagiarism detection systems work in simple terms.

---

## Plagiarism Detection

**Goal:** Find students who copied answers from each other.

### Step-by-Step Process

**Example scenario:**
```
Student A's answer: "Python is a programming language used for web development"
Student B's answer: "Python is a programming language used for web development"  
Student C's answer: "Java is compiled while Python is interpreted"
```

### Step 1: TF-IDF Vectorization

**TF-IDF** = Term Frequency - Inverse Document Frequency

This converts text into numbers (vectors):
- Words that appear often in ONE answer but rarely in OTHERS get higher scores
- Common words like "the", "is", "a" get low scores (they don't help distinguish answers)

```
Student A → [0.3, 0.5, 0.2, 0.4, ...]  (vector of numbers)
Student B → [0.3, 0.5, 0.2, 0.4, ...]  (very similar vector)
Student C → [0.1, 0.2, 0.6, 0.1, ...]  (different vector)
```

### Step 2: Cosine Similarity

Compares two vectors by measuring the angle between them:
- **1.0** = identical (0° angle)
- **0.0** = completely different (90° angle)

```
A vs B = 0.98 (98% similar) → FLAGGED FOR REVIEW
A vs C = 0.25 (25% similar) → OK
B vs C = 0.23 (23% similar) → OK
```

### Step 3: Threshold Check

- Default threshold: **85%**
- If similarity > 85%, the pair is flagged
- Educator manually reviews flagged pairs to confirm cheating

### Code Implementation

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

class PlagiarismDetector:
    def __init__(self, similarity_threshold=0.85):
        self.threshold = similarity_threshold
        self.vectorizer = TfidfVectorizer(stop_words='english')
    
    def check_submissions(self, answers):
        # Convert all answers to TF-IDF vectors
        texts = [answer.text for answer in answers]
        tfidf_matrix = self.vectorizer.fit_transform(texts)
        
        # Compare every pair
        similarity_matrix = cosine_similarity(tfidf_matrix)
        
        flagged_pairs = []
        for i in range(len(answers)):
            for j in range(i + 1, len(answers)):
                similarity = similarity_matrix[i][j]
                if similarity >= self.threshold:
                    flagged_pairs.append({
                        'student_1': answers[i].student,
                        'student_2': answers[j].student,
                        'similarity': similarity * 100  # Convert to percentage
                    })
        
        return flagged_pairs
```

---

## Mock Grading System

**Goal:** Automatically grade answers without using external AI APIs.

### MCQ and True/False Grading

Simple exact match comparison:

```python
def grade_mcq(student_choice, correct_answer, max_points):
    if student_choice == correct_answer:
        return max_points  # Full marks
    else:
        return 0  # Zero marks
```

### Short Answer and Essay Grading

Uses a combination of **TF-IDF similarity** and **keyword matching**.

**Example:**
```
Question: "What is a Python decorator?"

Expected Answer: "A decorator is a function that wraps another function 
                  to extend its behavior"

Student Answer: "Decorators wrap functions to add extra functionality"
```

#### Step 1: TF-IDF Similarity (60% weight)

```python
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.metrics.pairwise import cosine_similarity

def calculate_similarity(expected, student):
    vectorizer = TfidfVectorizer(stop_words='english')
    tfidf_matrix = vectorizer.fit_transform([expected, student])
    similarity = cosine_similarity(tfidf_matrix[0:1], tfidf_matrix[1:2])
    return similarity[0][0]

# Result: 0.72 (72% similar)
```

#### Step 2: Keyword Matching (40% weight)

```python
def calculate_keyword_score(expected, student):
    # Extract important words (remove common words)
    stop_words = {'the', 'a', 'an', 'is', 'are', 'to', 'for'}
    
    expected_keywords = set(expected.lower().split()) - stop_words
    student_keywords = set(student.lower().split()) - stop_words
    
    # Count matches
    matches = len(expected_keywords & student_keywords)
    total = len(expected_keywords)
    
    return matches / total if total > 0 else 0

# Expected keywords: {"decorator", "function", "wraps", "extend", "behavior"}
# Student keywords: {"decorators", "wrap", "functions", "add", "functionality"}
# Matches: 3 out of 5
# Result: 0.60 (60%)
```

#### Step 3: Combined Score

```python
def grade_short_answer(expected, student, max_points):
    similarity = calculate_similarity(expected, student)  # 0.72
    keyword_score = calculate_keyword_score(expected, student)  # 0.60
    
    # Weighted combination: 60% similarity, 40% keywords
    final_score = (similarity * 0.6) + (keyword_score * 0.4)
    # final_score = (0.72 * 0.6) + (0.60 * 0.4)
    # final_score = 0.432 + 0.24 = 0.672 (67.2%)
    
    points_earned = max_points * final_score
    # If max_points = 10: points_earned = 6.72
    
    return points_earned
```

### Essay Grading (Additional Factors)

For essays, we also consider:
- **Rubric matching**: Check if specific concepts from the grading rubric are mentioned
- **Length penalty**: Very short answers get penalized
- **Structure**: Presence of introduction/conclusion concepts

```python
def grade_essay(student_answer, expected_answer, max_points, rubric=None):
    # Base score from similarity
    similarity = calculate_similarity(expected_answer, student_answer)
    keyword_score = calculate_keyword_score(expected_answer, student_answer)
    
    # Rubric bonus (if rubric provided)
    rubric_score = 0
    if rubric:
        rubric_keywords = set(rubric.lower().split())
        student_words = set(student_answer.lower().split())
        rubric_matches = len(rubric_keywords & student_words)
        rubric_score = rubric_matches / len(rubric_keywords) if rubric_keywords else 0
    
    # Length check (penalize very short answers)
    min_words = 50
    word_count = len(student_answer.split())
    length_factor = min(1.0, word_count / min_words)
    
    # Combine all factors
    base_score = (similarity * 0.5) + (keyword_score * 0.3) + (rubric_score * 0.2)
    final_score = base_score * length_factor
    
    return max_points * final_score
```

---

## Why TF-IDF Instead of AI?

| Approach | Pros | Cons |
|----------|------|------|
| **TF-IDF (our choice)** | Fast, free, works offline, deterministic | Less "smart" than AI |
| **LLM (OpenAI/GPT)** | More accurate, understands context | Costs money, needs internet, slower |

### Reasons we chose TF-IDF:

1. **No external dependencies** - Works without internet connection
2. **Free** - No API costs, unlimited grading
3. **Fast** - Grades instantly (milliseconds vs seconds)
4. **Deterministic** - Same answer always gets the same score
5. **Assessment requirement** - The task specifically awards bonus points for building mock grading from scratch

### When to use LLM instead:

- Complex essay questions requiring deep understanding
- Questions with multiple valid answer formats
- When budget allows for API costs

---

## Grading Feedback Examples

The system generates automatic feedback based on the score:

| Score Range | Feedback |
|-------------|----------|
| 90-100% | "Excellent! Your answer demonstrates thorough understanding." |
| 70-89% | "Good answer. Covers most key concepts." |
| 50-69% | "Partial credit. Some key concepts are missing." |
| 25-49% | "Limited understanding demonstrated. Review the material." |
| 0-24% | "Answer does not address the question adequately." |

---

## Summary

### Plagiarism Detection Flow:
```
All Answers → TF-IDF Vectors → Pairwise Comparison → Flag if > 85% similar
```

### Grading Flow:
```
MCQ/TF: Exact match → Full or zero points

Short Answer: TF-IDF similarity (60%) + Keywords (40%) → Weighted score

Essay: Similarity (50%) + Keywords (30%) + Rubric (20%) × Length factor
```

Both systems use **scikit-learn's TfidfVectorizer** - a well-established machine learning library that's fast, reliable, and doesn't require external API calls.
