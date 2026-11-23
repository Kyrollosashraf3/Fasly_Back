"""Arabic name comparison - the one place that answers "is this the same boy?".

A child gets filed twice in two ways: his name is written differently
("مينا هاني" / "مينا هاني سعيد", "كرمينا" / "كيرمينا") or he lands under a second
class. Both are caught by comparing names after stripping everything a name
does not need, which is what this module does.

Two callers, one rule set:

    app.core.DA.check    reports the look-alikes already on file
    BoyService.create    asks before a new name is saved
"""

from __future__ import annotations

from collections import Counter
from difflib import SequenceMatcher

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from app.core.data.common import scope_boys
from app.features.boy.models.boy import Boy
from app.features.school_class.models.school_class import SchoolClass
from app.features.user.models.user import User

#: One sound, several keys: how a name happens to be typed must not matter.
_LETTERS = str.maketrans(
    {
        "أ": "ا",
        "إ": "ا",
        "آ": "ا",
        "ٱ": "ا",
        "ى": "ي",
        "ة": "ه",
        "ؤ": "و",
        "ئ": "ي",
    }
)

#: Harakat, tanwin, shadda and the tatweel filler carry nothing a name needs.
_MARKS = dict.fromkeys([*range(0x064B, 0x0653), 0x0640, 0x0670], None)

#: A boy is filed by three names - his own, his father's, his grandfather's.
NAME_PARTS = 3

#: How alike a new name and a name on file have to be before it is asked about.
WARN_THRESHOLD = 70


def normalise(value: object) -> str:
    """The comparison form of a name: no marks, one spelling per letter."""
    text = str(value or "").translate(_LETTERS).translate(_MARKS)
    return " ".join(text.split()).lower()


def signature(value: object) -> str:
    """Normalised name with its words sorted, so word order never matters."""
    return " ".join(sorted(normalise(value).split()))


def words(value: object) -> tuple:
    """Normalised name as the words were written: the first one is the given name."""
    return tuple(normalise(value).split())


def overlap(a: tuple, b: tuple) -> float:
    """Nesting: how much of the shorter name the longer one repeats.

    A directory written by hand drops a grandfather's name as often as it adds
    one, so "مينا هاني" and "مينا هاني سعيد" are the same child even though the
    letter-by-letter comparison of those two strings is only ~78% alike.

    Two names with different given names are not compared this way: brothers
    share a father's name, not a first name, and "ثابت ميلاد ثابت" beside
    "فيلومينا ميلاد ثابت" is two boys, not one entered twice.
    """
    if not a or not b or a[0] != b[0]:
        return 0.0
    shared = sum((Counter(a) & Counter(b)).values())
    return shared / min(len(a), len(b))


def similarity(
    a_text: str, b_text: str, a_words: tuple, b_words: tuple, floor: float
) -> tuple[float, str] | None:
    """How alike two names are (0..1), and which comparison found it.

    ``spelling`` is the letter-by-letter comparison, which catches a mistyped
    name ("كرمينا" beside "كيرمينا"). ``nested_name`` is the word comparison,
    which catches a name written with its patronymic added or left off. Each
    sees duplicates the other misses, and the word comparison is the cheaper,
    so it is asked first.

    ``real_quick_ratio`` and ``quick_ratio`` are upper bounds of ``ratio``, so a
    pair that can reach the threshold only through the letter comparison is
    dropped before that comparison runs - that is what keeps "every name
    against every name" affordable.
    """
    nested = overlap(a_words, b_words)
    if nested and nested >= floor:
        return nested, "nested_name"

    matcher = SequenceMatcher(None, a_text, b_text)
    if matcher.real_quick_ratio() < floor or matcher.quick_ratio() < floor:
        return None
    spelling = matcher.ratio()
    if spelling < floor:
        return None
    return spelling, "spelling"


def class_labels(db: Session) -> dict[int, str]:
    """Class id to grade label. A label leaks nothing, so this reads the whole
    table - ``SchoolClass`` carries no ``class_id`` of its own."""
    return {row.id: row.name for row in db.query(SchoolClass).all()}


def matches_for(
    db: Session, user: User, name: str, threshold: int = WARN_THRESHOLD
) -> dict:
    """The boys this login can already open whose name is ``name`` or looks like it.

    ``exact`` holds the same name written the same way, ``similar`` the ones at
    or above ``threshold`` - both answered from the names on file, never from
    anything the caller brings.
    """
    target_text = signature(name)
    target_words = words(name)
    floor = threshold / 100
    labels = class_labels(db)

    exact: list[dict] = []
    similar: list[dict] = []
    query = scope_boys(db, db.query(Boy), Boy, user, Boy.id)
    for boy in query.order_by(Boy.id).all():
        if signature(boy.boy_name) == target_text:
            exact.append(_hit(boy, 100.0, "same_name", labels))
            continue
        found = similarity(
            target_text, signature(boy.boy_name), target_words, words(boy.boy_name), floor
        )
        if found is not None:
            score, via = found
            similar.append(_hit(boy, round(score * 100, 1), via, labels))

    similar.sort(key=lambda hit: (-hit["score"], hit["boy_name"]))
    return {"threshold": threshold, "exact": exact, "similar": similar}


def _hit(boy: Boy, score: float, via: str, labels: dict) -> dict:
    return {
        "id": boy.id,
        "boy_name": boy.boy_name,
        "class_id": boy.class_id,
        "class_name": labels.get(boy.class_id),
        "score": score,
        "via": via,
    }


def ensure_full_name(name: str) -> None:
    """400 unless the name carries the three parts a boy is filed by."""
    if len(str(name or "").split()) < NAME_PARTS:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Boy name must be three parts: his name, his father's, his grandfather's.",
        )


def ensure_name_addable(
    db: Session, user: User, name: str, *, confirm_similar: bool = False
) -> None:
    """409 unless this name is a new boy's.

    100% alike is refused wherever it sits - one child cannot be filed twice,
    and the two rows would fight over his attendance. Anything from
    ``WARN_THRESHOLD`` up is put back as a question: the form shows the names
    on file and asks the person to confirm or to open the boy already there,
    and the retry arrives with ``confirm_similar``.

    The payload carries ``code`` and ``matches`` rather than a sentence,
    because the answer is a choice, not an error.
    """
    found = matches_for(db, user, name)
    if found["exact"]:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "boy_name_taken", "matches": found["exact"]},
        )
    if found["similar"] and not confirm_similar:
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail={"code": "boy_name_similar", "matches": found["similar"]},
        )
