"""
Tagicus - Cross-Reference Engine

Cross-references all sources with smart weighting:
- When ID3 tags and filename agree, their combined signal gets boosted
  because a human already verified that data
- For year conflicts, prefers earliest year (original release)
- For album conflicts, prefers the album from the earliest year source
- More sources agreeing = higher confidence
"""

from thefuzz import fuzz
from models import SourceResult, FieldVote

FIELDS = ["artist", "title", "album", "year", "track", "genre"]
FUZZY_THRESHOLD = 80

# Sources that represent local/human-verified data
LOCAL_SOURCES = {"id3_tags", "filename"}

# Priority order for picking the representative value when sources agree
SOURCE_PRIORITY = ["id3_tags", "acoustid", "musicbrainz", "deezer", "audiodb", "discogs", "wikidata", "filename"]


def cross_reference(results):
    votes = []

    # Pre-check: do local sources (ID3 + filename) agree on core fields?
    local_agreement = _check_local_agreement(results)

    for fn in FIELDS:
        vote = FieldVote(field_name=fn)

        # Collect each source's value
        for r in results:
            v = getattr(r, fn, None)
            if v is not None:
                vote.votes[r.source] = str(v)

        if not vote.votes:
            votes.append(vote)
            continue

        # Group similar values using fuzzy matching
        groups = _group_similar(list(vote.votes.values()), fn)

        # Count votes per group, with smart weighting
        group_scores = []
        for group in groups:
            score = 0
            members = []
            for source, value in vote.votes.items():
                if _value_in_group(value, group, fn):
                    members.append(source)
                    if source in LOCAL_SOURCES:
                        # Local sources get a weight boost when they agree with each other
                        if fn in local_agreement:
                            score += 2.0  # Double weight when locals agree
                        else:
                            score += 1.0
                    else:
                        score += 1.0
            group_scores.append((group, score, members))

        # Pick the group with the highest score
        group_scores.sort(key=lambda x: x[1], reverse=True)
        best_group, best_score, best_members = group_scores[0]

        # Pick the representative value
        if fn == "year":
            vote.best_value = _pick_earliest_year(vote.votes, best_members)
        elif fn == "album":
            vote.best_value = _pick_album_by_earliest_year(vote.votes, results, best_members)
        else:
            vote.best_value = _pick_by_priority(vote.votes, best_group)

        total_votes = len(vote.votes)
        agreeing_votes = len(best_members)
        vote.agreement = agreeing_votes / total_votes if total_votes > 0 else 0
        vote.conflict = len(group_scores) > 1

        votes.append(vote)

    return votes


def _check_local_agreement(results):
    """Check which fields have agreement between ID3 tags and filename."""
    local_results = [r for r in results if r.source in LOCAL_SOURCES]
    if len(local_results) < 2:
        return set()

    agreed_fields = set()
    for fn in FIELDS:
        values = []
        for r in local_results:
            v = getattr(r, fn, None)
            if v is not None:
                values.append(str(v))
        if len(values) >= 2:
            # Check if at least 2 local sources agree
            for i in range(len(values)):
                for j in range(i + 1, len(values)):
                    if fn in ("year", "track"):
                        if values[i] == values[j]:
                            agreed_fields.add(fn)
                    else:
                        if fuzz.ratio(values[i].lower(), values[j].lower()) >= FUZZY_THRESHOLD:
                            agreed_fields.add(fn)
    return agreed_fields


def _value_in_group(value, group, field_name):
    if field_name in ("year", "track"):
        return value in group
    for g in group:
        if fuzz.ratio(value.lower(), g.lower()) >= FUZZY_THRESHOLD:
            return True
    return False


def _pick_by_priority(votes_dict, best_group):
    """Pick value from the highest-priority source in the winning group."""
    for source in SOURCE_PRIORITY:
        if source in votes_dict and _value_in_group(votes_dict[source], best_group, "text"):
            return votes_dict[source]
    return best_group[0]


def _pick_earliest_year(year_votes, best_members=None):
    source_filter = best_members if best_members else year_votes.keys()
    years = []
    for source in source_filter:
        if source in year_votes:
            try:
                years.append((int(year_votes[source]), year_votes[source]))
            except ValueError:
                continue
    if years:
        years.sort(key=lambda x: x[0])
        return years[0][1]
    return list(year_votes.values())[0]


def _pick_album_by_earliest_year(album_votes, results, best_members=None):
    source_filter = best_members if best_members else album_votes.keys()
    earliest_year = 9999
    earliest_source = None
    for r in results:
        if r.year and r.source in source_filter and r.source in album_votes:
            try:
                yi = int(r.year)
                if yi < earliest_year:
                    earliest_year = yi
                    earliest_source = r.source
            except ValueError:
                continue
    if earliest_source and earliest_source in album_votes:
        return album_votes[earliest_source]
    for s in SOURCE_PRIORITY:
        if s in album_votes:
            return album_votes[s]
    return list(album_votes.values())[0]


def _group_similar(values, fn):
    if not values:
        return []
    if fn in ("year", "track"):
        g = {}
        for v in values:
            if v in g:
                g[v].append(v)
            else:
                g[v] = [v]
        return list(g.values())
    groups = []
    for value in values:
        placed = False
        for group in groups:
            if fuzz.ratio(value.lower(), group[0].lower()) >= FUZZY_THRESHOLD:
                group.append(value)
                placed = True
                break
        if not placed:
            groups.append([value])
    return groups
