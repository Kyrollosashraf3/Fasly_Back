"""check.py - data-quality checks over the boys directory.

The same boy gets entered twice in two ways: his name is written differently
("مينا هاني" / "مينا هاني سعيد", "كرمينا" / "كيرمينا") or he is filed under two
classes. Both are found here by comparing every name against every other name
and keeping the pairs that look alike at or above a threshold the caller picks.

The comparison itself is ``app.core.data.names`` - the same one a new boy is
checked against the directory before he is saved.

Nothing is renamed or deleted by this module - it only reports. Merging two
records is a person's decision, made from the boys screen with both rows in
front of them.

Scoping is the boys' own: a class amin only ever sees his class, so a duplicate
is only reported between boys he can already open.
"""

from __future__ import annotations

from app.core.DA.dashboard import _iso
from app.core.data.base import BaseService
from app.core.data.common import ensure_staff, scope_boys
from app.core.data.names import class_labels, signature, similarity, words
from app.models.boy import Boy


class NameCheckService(BaseService):
    """Duplicate and near-duplicate boy names. Read-only."""

    def _boys(self, class_id: int | None) -> list[Boy]:
        query = scope_boys(self.db, self.db.query(Boy), Boy, self.user, Boy.id)
        if class_id is not None:
            self.ensure_class(class_id)
            query = query.filter(Boy.class_id == class_id)
        return query.order_by(Boy.id).all()

    def _labels(self) -> dict[int, str]:
        return class_labels(self.db)

    def duplicates(
        self, threshold: int = 80, scope: str = "all", class_id: int | None = None
    ) -> dict:
        """Every pair of boys whose names are at least ``threshold``% alike.

        ``scope`` decides which pairs count: boys filed in one class
        (``same_class``), the same name filed under two classes
        (``diff_class``) or both (``all``).
        """
        ensure_staff(self.user)
        boys = self._boys(class_id)
        floor = threshold / 100
        signatures = {b.id: signature(b.boy_name) for b in boys}
        word_lists = {b.id: words(b.boy_name) for b in boys}

        pairs: list[dict] = []
        for index, a in enumerate(boys):
            for other in boys[index + 1 :]:
                if scope == "same_class" and a.class_id != other.class_id:
                    continue
                if scope == "diff_class" and a.class_id == other.class_id:
                    continue
                found = similarity(
                    signatures[a.id],
                    signatures[other.id],
                    word_lists[a.id],
                    word_lists[other.id],
                    floor,
                )
                if found is None:
                    continue
                score, via = found
                pairs.append(
                    {
                        "a": a.id,
                        "b": other.id,
                        "score": round(score * 100, 1),
                        "via": via,
                        "exact": signatures[a.id] == signatures[other.id],
                        "same_class": a.class_id == other.class_id,
                    }
                )

        labels = self._labels()
        return {
            "threshold": threshold,
            "scope": scope,
            "class_id": class_id,
            "checked": len(boys),
            "pair_count": len(pairs),
            "groups": self._clusters(pairs, {b.id: b for b in boys}, labels),
        }

    @staticmethod
    def _clusters(pairs: list[dict], by_id: dict, labels: dict) -> list[dict]:
        """Pairs that share a boy become one card, so three spellings of the
        same child are handled once instead of three times."""
        parent: dict[int, int] = {}

        def find(boy_id: int) -> int:
            parent.setdefault(boy_id, boy_id)
            root = boy_id
            while parent[root] != root:
                root = parent[root]
            while parent[boy_id] != root:
                parent[boy_id], boy_id = root, parent[boy_id]
            return root

        for pair in pairs:
            ra, rb = find(pair["a"]), find(pair["b"])
            if ra != rb:
                parent[rb] = ra

        members: dict[int, list[int]] = {}
        for boy_id in list(parent):
            members.setdefault(find(boy_id), []).append(boy_id)

        groups = []
        for ids in members.values():
            ids.sort()
            inside = [p for p in pairs if p["a"] in ids and p["b"] in ids]
            best = max(inside, key=lambda p: p["score"])
            groups.append(
                {
                    "key": "-".join(str(i) for i in ids),
                    "score": best["score"],
                    "via": best["via"],
                    "exact": any(p["exact"] for p in inside),
                    "same_class": all(p["same_class"] for p in inside),
                    "members": [
                        {
                            "id": by_id[i].id,
                            "boy_name": by_id[i].boy_name,
                            "class_id": by_id[i].class_id,
                            "class_name": labels.get(by_id[i].class_id),
                            "birth_date": _iso(by_id[i].birth_date),
                            "age": by_id[i].age,
                            "phone": by_id[i].phone,
                            "teacher_name": by_id[i].teacher_name,
                            "issue_flag": by_id[i].issue_flag,
                        }
                        for i in ids
                    ],
                }
            )
        # The likeliest mistakes first: one name written twice, then the closest.
        groups.sort(
            key=lambda g: (-int(g["exact"]), -g["score"], g["members"][0]["boy_name"])
        )
        return groups
