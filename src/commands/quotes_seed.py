"""
quotes_seed.py — Coding Quotes Seeder

Fetches coding and developer quotes from online sources and populates
the local SQLite database (`quotes` table) for use in focus receipts
and reward slips.

Usage:
    python -m src.commands.quotes_seed
    python -m src.commands.quotes_seed --list
    python -m src.commands.quotes_seed --reset
"""

from __future__ import annotations

import argparse
import sys
import requests

from src.db import clear_quotes, count_quotes, insert_quotes

MAX_QUOTE_LEN = 120

# Built-in curated fallback list of famous short programming & tech quotes
FALLBACK_CODING_QUOTES = [
    {"text": "First, solve the problem. Then, write the code.", "author": "John Johnson"},
    {"text": "Experience is the name everyone gives to their mistakes.", "author": "Oscar Wilde"},
    {"text": "Simplicity is the soul of efficiency.", "author": "Austin Freeman"},
    {"text": "Make it work, make it right, make it fast.", "author": "Kent Beck"},
    {"text": "Code is like humor. When you have to explain it, it’s bad.", "author": "Cory House"},
    {"text": "Fix the cause, not the symptom.", "author": "Steve Maguire"},
    {"text": "Optimism is an occupational hazard of programming.", "author": "Kent Beck"},
    {"text": "When to use pattern matching? Always.", "author": "Erik Meijer"},
    {"text": "Before software can be reusable it first has to be usable.", "author": "Ralph Johnson"},
    {"text": "Deleted code is debugged code.", "author": "Jeff Sickel"},
    {"text": "Simplicity is prerequisite for reliability.", "author": "Edsger W. Dijkstra"},
    {"text": "Program testing shows the presence of bugs, not their absence!", "author": "Edsger W. Dijkstra"},
    {"text": "Make it fail fast.", "author": "Martin Fowler"},
    {"text": "Good programmers write code that humans can understand.", "author": "Martin Fowler"},
    {"text": "Truth can only be found in one place: the code.", "author": "Robert C. Martin"},
    {"text": "Clean code always looks like it was written by someone who cares.", "author": "Robert C. Martin"},
    {"text": "Talk is cheap. Show me the code.", "author": "Linus Torvalds"},
    {"text": "Software is a great combination between artistry and engineering.", "author": "Bill Gates"},
    {"text": "Measuring progress by lines of code is like measuring aircraft by weight.", "author": "Bill Gates"},
    {"text": "The most important property of a program is whether it fulfills user intent.", "author": "C.A.R. Hoare"},
    {"text": "Perfection is achieved when there is nothing left to take away.", "author": "Antoine de Saint-Exupéry"},
    {"text": "Good code is its own best documentation.", "author": "Steve McConnell"},
    {"text": "The best error message is the one that never shows up.", "author": "Thomas Fuchs"},
    {"text": "Don't write code that you can't test.", "author": "Unknown"},
    {"text": "Walking on water and software specs are easy if both are frozen.", "author": "Edward V. Berard"},
    {"text": "It's not a bug – it's an undocumented feature.", "author": "Anonymous"},
    {"text": "One man's constant is another man's variable.", "author": "Alan J. Perlis"},
    {"text": "Two hard things in CS: cache invalidation and naming things.", "author": "Phil Karlton"},
    {"text": "Programs must be written for people to read.", "author": "Abelson & Sussman"},
    {"text": "Programming is about what you can figure out.", "author": "Chris Pine"},
    {"text": "The only way to go fast is to go well.", "author": "Robert C. Martin"},
    {"text": "Refactor early, refactor often.", "author": "Anonymous"},
    {"text": "Computers are fast; programmers keep it slow.", "author": "Anonymous"},
    {"text": "Debugging is twice as hard as writing the code.", "author": "Brian W. Kernighan"},
    {"text": "Controlling complexity is the essence of programming.", "author": "Brian W. Kernighan"},
    {"text": "Simplicity is subtracting the obvious and adding the meaningful.", "author": "John Maeda"},
    {"text": "If it works, don't touch it.", "author": "Developer Proverb"},
    {"text": "Computers follow instructions, they don't read minds.", "author": "Donald Knuth"},
    {"text": "Code never lies, comments sometimes do.", "author": "Ron Jeffries"},
    {"text": "Always code as if the maintainer knows where you live.", "author": "John Woods"},
    {"text": "Testing leads to failure, failure leads to understanding.", "author": "Burt Rutan"},
    {"text": "Every great developer got there by solving hard problems.", "author": "Patrick McKenzie"},
    {"text": "You can't blame gravity for falling in love with clean code.", "author": "Anonymous"},
    {"text": "Stay hungry, stay foolish.", "author": "Steve Jobs"},
    {"text": "Details matter, it's worth waiting to get it right.", "author": "Steve Jobs"},
    {"text": "Innovation distinguishes between a leader and a follower.", "author": "Steve Jobs"},
    {"text": "Keep it simple, stupid.", "author": "Kelly Johnson"},
    {"text": "Premature optimization is the root of all evil.", "author": "Donald Knuth"},
    {"text": "Knowledge is power, but code is action.", "author": "Anonymous"},
    {"text": "Chaos is the neighbor of undocumented legacy code.", "author": "Dev Wisdom"},
    {"text": "Functions should do one thing and do it well.", "author": "Robert C. Martin"},
    {"text": "Duplication is the primary enemy of a well-designed system.", "author": "Robert C. Martin"},
    {"text": "Without requirements or design, programming is the art of adding bugs.", "author": "Louis Srygley"},
    {"text": "Java is to JavaScript what car is to carpet.", "author": "Chris Heilmann"},
    {"text": "Software undergoes beta testing right before it's released.", "author": "Developer Joke"},
    {"text": "There is no code faster than no code.", "author": "Kevlin Henney"},
    {"text": "To iterate is human, to recurse divine.", "author": "L. Peter Deutsch"},
    {"text": "The computer was born to solve problems that did not exist before.", "author": "Bill Gates"},
    {"text": "Software is like entropy: It is difficult to grasp, weighs nothing, and obeys the 2nd law.", "author": "Norman Augustine"},
    {"text": "Complexity kills. It sucks the life out of developers.", "author": "Ray Ozzie"},
    {"text": "Failure is not an option — it comes bundled with software.", "author": "Unknown"},
    {"text": "A user interface is like a joke. If you have to explain it, it’s not that good.", "author": "Martin LeBlanc"},
    {"text": "If debugging is the process of removing bugs, programming must be putting them in.", "author": "Edsger W. Dijkstra"},
    {"text": "Real programmers don't comment their code. If it was hard to write, it should be hard to read.", "author": "Anonymous"},
    {"text": "Small acts of refactoring add up to massive codebase speedups.", "author": "Dev Motto"},
    {"text": "Write code as if you're building a foundation for a skyscraper.", "author": "Tech Maxim"},
    {"text": "Code is thought made visible.", "author": "Anonymous"},
    {"text": "Don't comment bad code — rewrite it.", "author": "Brian W. Kernighan"},
    {"text": "The function of good software is to make the complex appear simple.", "author": "Grady Booch"},
    {"text": "Give a man a program, frustrate him for a day. Teach him to program, frustrate him for a lifetime.", "author": "Waseem Latif"},
    {"text": "Testing isn't about finding bugs, it's about building confidence.", "author": "Anonymous"},
    {"text": "Standardization is the enemy of innovation, but the friend of maintainability.", "author": "Dev Axiom"},
    {"text": "Code that works tomorrow is better than code that works today.", "author": "Anonymous"},
    {"text": "The best code is no code at all.", "author": "Jeff Atwood"},
    {"text": "Computers are useless. They can only give you answers.", "author": "Pablo Picasso"},
    {"text": "Simplicity before generality, use before reuse.", "author": "Doug McIlroy"},
    {"text": "Code readability is a feature, not a luxury.", "author": "Dev Rule"},
    {"text": "First rule of refactoring: don't break existing functionality.", "author": "Dev Rule"},
    {"text": "Automate everything that can be automated.", "author": "Dev Ops Maxim"},
    {"text": "Continuous learning is the developer's cheat code.", "author": "Tech Proverb"},
    {"text": "Fix the root cause, not the stack trace.", "author": "Dev Maxim"},
    {"text": "Ship early, iterate fast.", "author": "Startup Proverb"},
    {"text": "A compiler error is a friend warning you before the production fire.", "author": "Dev Wisdom"},
    {"text": "Good architecture makes decisions easy to defer.", "author": "Robert C. Martin"},
    {"text": "A good programmer looks both ways before crossing a one-way street.", "author": "Doug Linder"},
    {"text": "Computers make it easy to do things fast, but not necessarily right.", "author": "Dev Thought"},
    {"text": "Code is an asset, but lines of code are a liability.", "author": "Dev Thought"},
    {"text": "The secret to fast code is doing less work.", "author": "Performance Rule"},
    {"text": "Learn the rules so you know how to break them properly.", "author": "Dalai Lama"},
    {"text": "Focus on the core loop before adding polish.", "author": "Game Dev Rule"},
    {"text": "Memory leaks are silent thieves.", "author": "Systems Rule"},
    {"text": "In programming, clarity trumps cleverness every single time.", "author": "Dev Principle"},
    {"text": "Code, sleep, repeat. But don't forget to push.", "author": "Dev Life"},
    {"text": "Unit tests are your safety net when taking big leaps.", "author": "Dev Rule"},
    {"text": "Great software requires great discipline.", "author": "Dev Thought"},
    {"text": "Stay curious. Keep building.", "author": "Dev Motto"},
    {"text": "One break at a time, one bug at a time.", "author": "Dev Motto"},
    {"text": "Solve it on paper before writing a line of code.", "author": "Dev Advice"},
    {"text": "Type safety saves hours of debugging.", "author": "Dev Experience"},
    {"text": "Version control is your time machine.", "author": "Dev Proverb"},
    {"text": "Build tools that make you faster tomorrow.", "author": "Tooling Rule"},
    {"text": "Edge cases are where software lives or dies.", "author": "QA Proverb"},
    {"text": "Keep your methods small and focused.", "author": "Clean Code"},
    {"text": "Name variables for humans, not compilers.", "author": "Clean Code"},
    {"text": "Immutable state brings peace of mind.", "author": "FP Axiom"},
    {"text": "Concurrency is hard, but synchronization is harder.", "author": "Systems Principle"},
    {"text": "Premature abstractions are as dangerous as premature optimizations.", "author": "Dev Wisdom"},
    {"text": "Fail noisy during development, fail graceful in production.", "author": "Dev Principle"},
    {"text": "Design for maintainability first.", "author": "Dev Principle"},
    {"text": "Log with purpose, not with noise.", "author": "Dev Practice"},
    {"text": "A well-tested module is a trustworthy module.", "author": "Dev Practice"},
    {"text": "Master your editor, master your speed.", "author": "Dev Practice"},
    {"text": "Keyboard shortcuts are compound interest for your hands.", "author": "Dev Tip"},
    {"text": "Understand the problem before hunting for solutions.", "author": "Dev Tip"},
    {"text": "Write code today that you won't hate in six months.", "author": "Dev Tip"},
    {"text": "Every line of code is a contract with your future self.", "author": "Dev Tip"},
    {"text": "Complexity is a choice.", "author": "Dev Maxim"},
    {"text": "Consistency beats cleverness.", "author": "Dev Maxim"},
    {"text": "Discipline is doing what needs to be done even when you don't feel like it.", "author": "Proverb"},
    {"text": "Action cures anxiety. Code cures doubt.", "author": "Dev Mantra"},
    {"text": "Zero warnings in the build log.", "author": "Dev Standard"},
    {"text": "Your future self will thank you for documenting this.", "author": "Dev Note"},
    {"text": "Focus is saying no to a hundred good ideas.", "author": "Steve Jobs"},
    {"text": "Small daily gains result in huge lifetime achievements.", "author": "Proverb"},
    {"text": "Ship code, learn, iterate.", "author": "Dev Mantra"},
    {"text": "Lock in and finish the task.", "author": "Dev Mantra"},
    {"text": "One function, one responsibility.", "author": "SOLID Principle"},
    {"text": "Open for extension, closed for modification.", "author": "SOLID Principle"},
    {"text": "Interfaces should be client-specific.", "author": "SOLID Principle"},
    {"text": "Depend on abstractions, not concretions.", "author": "SOLID Principle"},
    {"text": "High cohesion, low coupling.", "author": "Software Design"},
    {"text": "Do the simplest thing that could possibly work.", "author": "XP Principle"},
    {"text": "You aren't gonna need it (YAGNI).", "author": "XP Principle"},
    {"text": "Don't repeat yourself (DRY).", "author": "Pragmatic Programmer"},
    {"text": "Keep your code DRY and your tests WET.", "author": "Dev Rule"},
    {"text": "The debugger is a diagnostic tool, not a design tool.", "author": "Pragmatic Programmer"},
    {"text": "Fix bugs when you find them, not later.", "author": "Pragmatic Programmer"},
    {"text": "Test your boundary conditions.", "author": "Pragmatic Programmer"},
    {"text": "Use version control for everything.", "author": "Pragmatic Programmer"},
    {"text": "Don't panic when the build breaks.", "author": "Dev Advice"},
    {"text": "Read the documentation before assuming it's broken.", "author": "Dev Advice"},
    {"text": "Check the logs first.", "author": "Dev Advice"},
    {"text": "Understand the execution flow before patching.", "author": "Dev Advice"},
    {"text": "A good test suite is the ultimate documentation.", "author": "Dev Advice"},
    {"text": "Think twice, code once.", "author": "Dev Advice"},
    {"text": "Measure twice, cut once.", "author": "Craftsman Rule"},
    {"text": "Refactoring without tests is just changing code.", "author": "Martin Fowler"},
    {"text": "Legacy code is code without tests.", "author": "Michael Feathers"},
    {"text": "Make the change easy, then make the easy change.", "author": "Kent Beck"},
    {"text": "Write tests to fail before writing code to pass.", "author": "TDD Rule"},
    {"text": "Red, Green, Refactor.", "author": "TDD Mantra"},
    {"text": "Clean code is simple and direct.", "author": "Grady Booch"},
    {"text": "Bad code brings down good teams.", "author": "Dev Maxim"},
    {"text": "Technical debt is high-interest loan on your future speed.", "author": "Dev Maxim"},
    {"text": "Pay down tech debt regularly.", "author": "Dev Rule"},
    {"text": "A crash dump is a treasure map.", "author": "Reverse Engineer Proverb"},
    {"text": "Assembly is the language of truth.", "author": "Reverse Engineer Proverb"},
    {"text": "Every binary has secrets waiting to be decompiled.", "author": "Hacker Proverb"},
    {"text": "Inspect the stack, follow the registers.", "author": "Hacker Proverb"},
    {"text": "No protection is unbreakable given enough patience.", "author": "Security Proverb"},
    {"text": "Understand the memory layout to understand the exploit.", "author": "Game Hacker Proverb"},
    {"text": "Pointers are addresses, not magic.", "author": "C Proverb"},
    {"text": "Check your allocations and free your memory.", "author": "C Proverb"},
    {"text": "Buffer overflows are preventable by bound checks.", "author": "Security Rule"},
    {"text": "Sanitize your inputs always.", "author": "Security Rule"},
    {"text": "Never trust client-side data.", "author": "Web Security Rule"},
    {"text": "Defense in depth is the gold standard.", "author": "Security Principle"},
    {"text": "Least privilege access everywhere.", "author": "Security Principle"},
    {"text": "Keep learning, keep reversing, keep building.", "author": "Hacker Motto"},
    {"text": "The best way to understand a system is to break it.", "author": "Hacker Motto"},
    {"text": "Reverse engineering is curiosity with a disassembler.", "author": "Hacker Motto"},
    {"text": "Patience and IDA Pro solve all problems.", "author": "RE Motto"},
    {"text": "x86 or ARM, the logic remains machine code.", "author": "RE Motto"},
    {"text": "Breakpoints are your flashlights in dark binaries.", "author": "RE Motto"},
    {"text": "Find the entry point, follow the control flow.", "author": "RE Rule"},
    {"text": "Static analysis shows the map, dynamic analysis shows the journey.", "author": "RE Principle"},
    {"text": "Hook the function, control the game.", "author": "Game Hacker Maxim"},
    {"text": "Memory scanning is step one of game hacking.", "author": "Game Hacker Maxim"},
    {"text": "Find the base pointer, calculate the offsets.", "author": "Game Hacker Rule"},
    {"text": "NOP the instruction to bypass the check.", "author": "RE Proverb"},
    {"text": "XORing with zero is clearing a register.", "author": "ASM Fact"},
    {"text": "Stack frames keep function calls honest.", "author": "ASM Fact"},
    {"text": "EIP/RIP points to the next step forward.", "author": "ASM Fact"},
    {"text": "Respect the ABI, preserve the registers.", "author": "ASM Rule"},
    {"text": "Code with intent. Execute with precision.", "author": "Dev Motto"},
    {"text": "Stay disciplined. Push code daily.", "author": "Dev Motto"}
]


def fetch_programming_quotes_github() -> list[dict]:
    """Fetch from open-source GitHub programming quotes JSON backup."""
    url = "https://raw.githubusercontent.com/skolakoda/programming-quotes-api/master/backup/quotes.json"
    results: list[dict] = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                text = item.get("en") or item.get("quote") or item.get("text")
                author = item.get("author")
                if text:
                    results.append({"text": text.strip(), "author": author.strip() if author else None, "source": "programming-quotes-github"})
    except Exception as e:
        print(f"Notice: Could not fetch from GitHub quotes source: {e}")
    return results


def fetch_dummyjson_quotes() -> list[dict]:
    """Fetch quotes from dummyjson public endpoint."""
    url = "https://dummyjson.com/quotes?limit=150"
    results: list[dict] = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        quotes = data.get("quotes", [])
        for item in quotes:
            text = item.get("quote")
            author = item.get("author")
            if text:
                results.append({"text": text.strip(), "author": author.strip() if author else None, "source": "dummyjson"})
    except Exception as e:
        print(f"Notice: Could not fetch from dummyjson source: {e}")
    return results


def fetch_quotable_quotes() -> list[dict]:
    """Fetch technology/inspirational quotes from quotable.io or type.fit."""
    url = "https://type.fit/api/quotes"
    results: list[dict] = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data:
                text = item.get("text")
                author = item.get("author")
                if author and "," in author:
                    author = author.split(",")[0]
                if text:
                    results.append({"text": text.strip(), "author": author.strip() if author else None, "source": "type.fit"})
    except Exception as e:
        print(f"Notice: Could not fetch from type.fit source: {e}")
    return results


TECH_KEYWORDS = {
    "code", "coding", "program", "programmer", "programming", "developer", "software",
    "computer", "bug", "debug", "debugging", "algorithm", "data", "function", "feature",
    "system", "build", "logic", "hack", "hacker", "hacking", "tech", "technology",
    "science", "test", "testing", "error", "solution", "solve", "problem", "design",
    "keyboard", "screen", "web", "app", "application", "digital", "architecture",
    "refactor", "git", "commit", "push", "pull", "deploy", "server", "database",
    "cache", "hardware", "cpu", "memory", "byte", "bit", "binary", "syntax", "compiler",
    "language", "framework", "library", "script", "terminal", "console", "cli",
    "gui", "interface", "api", "rest", "json", "python", "java", "c", "cpp", "js",
    "rust", "go", "php", "html", "css", "sql", "linux", "unix", "windows", "machine",
    "robot", "ai", "intelligence", "network", "internet", "cloud", "security",
    "cipher", "crypto", "matrix", "vector", "array", "string", "loop", "variable",
    "object", "class", "method", "thread", "process", "stack", "heap", "queue",
    "recursion", "iteration", "efficiency", "optimization", "clean", "simple",
    "simplicity", "refactoring", "documentation", "specification", "architecture",
    "discipline", "focus", "work", "craft", "engineering", "engineer", "tool"
}


def filter_quotes(quotes_list: list[dict], max_len: int = MAX_QUOTE_LEN) -> list[dict]:
    """Filter out quotes that are too long, empty, or not tech/coding/dev related."""
    valid: list[dict] = []
    seen = set()
    for q in quotes_list:
        text = q.get("text", "").strip()
        if not text:
            continue
        if len(text) > max_len:
            continue
        if text.lower() in seen:
            continue

        # For fallback/github programming sources, keep directly.
        # For general sources, check if any tech/coding keyword or author is present.
        src = q.get("source", "")
        if "fallback" in src or "programming" in src:
            is_relevant = True
        else:
            words = set(text.lower().replace(".", " ").replace(",", " ").replace("-", " ").split())
            is_relevant = bool(words & TECH_KEYWORDS)

        if not is_relevant:
            continue

        seen.add(text.lower())
        valid.append({
            "text": text,
            "author": q.get("author") or "Unknown",
            "source": src or "fallback",
        })
    return valid


def fetch_dwyl_quotes() -> list[dict]:
    """Fetch quotes from dwyl/quotes repository on GitHub."""
    url = "https://raw.githubusercontent.com/dwyl/quotes/main/quotes.json"
    results: list[dict] = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data[:500]:
                text = item.get("text")
                author = item.get("author")
                if text:
                    results.append({"text": text.strip(), "author": author.strip() if author else None, "source": "dwyl/quotes"})
    except Exception as e:
        print(f"Notice: Could not fetch from dwyl/quotes source: {e}")
    return results


def fetch_jamesft_quotes() -> list[dict]:
    """Fetch quotes from JamesFT/Database-Quotes-JSON repository on GitHub."""
    url = "https://raw.githubusercontent.com/JamesFT/Database-Quotes-JSON/master/quotes.json"
    results: list[dict] = []
    try:
        resp = requests.get(url, timeout=10)
        resp.raise_for_status()
        data = resp.json()
        if isinstance(data, list):
            for item in data[:500]:
                text = item.get("quoteText")
                author = item.get("quoteAuthor")
                if text:
                    results.append({"text": text.strip(), "author": author.strip() if author else None, "source": "jamesft/quotes"})
    except Exception as e:
        print(f"Notice: Could not fetch from jamesft/quotes source: {e}")
    return results


def seed_quotes() -> int:
    """Fetch from all sources and seed the database."""
    print("Fetching coding & tech quotes from online sources...")
    all_raw: list[dict] = []

    # Include fallback list
    for item in FALLBACK_CODING_QUOTES:
        all_raw.append({"text": item["text"], "author": item["author"], "source": "fallback"})

    # Online sources
    all_raw.extend(fetch_programming_quotes_github())
    all_raw.extend(fetch_dummyjson_quotes())
    all_raw.extend(fetch_quotable_quotes())
    all_raw.extend(fetch_dwyl_quotes())
    all_raw.extend(fetch_jamesft_quotes())

    filtered = filter_quotes(all_raw, max_len=MAX_QUOTE_LEN)
    print(f"Filtered {len(filtered)} quotes matching criteria (length <= {MAX_QUOTE_LEN} chars).")

    inserted = insert_quotes(filtered)
    total = count_quotes()
    print(f"Seeded {inserted} new quotes. Total in database: {total}")
    return total


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(
        description="Seed coding and developer quotes into local database"
    )
    parser.add_argument(
        "--reset",
        action="store_true",
        help="Clear existing quotes in database before seeding",
    )
    parser.add_argument(
        "--list",
        action="store_true",
        help="Display quote count and sample quotes",
    )
    args = parser.parse_args(argv)

    if args.list:
        total = count_quotes()
        print(f"Quotes in database: {total}")
        if total > 0:
            from src.db import get_random_quote
            print("\nSample quotes:")
            for i in range(min(5, total)):
                print(f"  {i+1}. {get_random_quote()}")
        return

    if args.reset:
        print("Clearing existing quotes...")
        clear_quotes()

    seed_quotes()


if __name__ == "__main__":
    main()
