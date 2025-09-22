import os, sys, json, requests
from datetime import datetime, timedelta, date

BASE   = os.environ.get("LOCALIST_BASE", "https://calendar.usc.edu")
PP     = int(os.environ.get("LOCALIST_PP", "100"))
GROUP  = int(os.environ.get("LOCALIST_GROUP_ID", "7761"))

OUT = sys.argv[1] if len(sys.argv) > 1 else "events.json"

def to_iso(dt):
    if not dt:
        return ""
    try:
        return datetime.fromisoformat(dt.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except Exception:
        return dt.split("T", 1)[0]

def fetch_page(page, start_str, days):
    url = f"{BASE}/api/2/events"
    params = {
        "start": start_str,
        "days": days,
        "pp": PP,
        "page": page,
        "group_id": GROUP,
    }
    r = requests.get(url, params=params, timeout=30)
    r.raise_for_status()
    return r.json()

def main():
    # ----- Compute a ±7 day window around today -----
    today = date.today()
    start_dt = today - timedelta(days=7)      # begin 7 days before today
    start_str = start_dt.strftime("%Y-%m-%d")
    days = 15                                 # covers start .. start+14 (15 days total)

    # ----- Load existing (append-only) -----
    existing = []
    seen = set()
    if os.path.exists(OUT):
        with open(OUT, "r", encoding="utf-8") as f:
            try:
                existing = json.load(f)
            except Exception:
                existing = []
        for e in existing:
            key = (e.get("title"), e.get("date"))
            seen.add(key)

    new_events = []

    page = 1
    while True:
        payload = fetch_page(page, start_str, days)
        events = payload.get("events", [])
        if not events:
            break

        for wrapper in events:
            ev = wrapper.get("event", {})
            title = (ev.get("title") or "").strip()

            # Only include RTG events
            if "rtg" not in title.lower():
                continue

            instances = ev.get("event_instances") or []
            start = ""
            if instances:
                inst = instances[0].get("event_instance", {})
                start = inst.get("start") or ""

            date_iso = to_iso(start)
            key = (title, date_iso)
            if key in seen:
                continue
            seen.add(key)

            where = ev.get("location_name") or ev.get("venue_name") or ""
            types = ev.get("event_types") or []
            etype = types[0]["name"] if types and "name" in types[0] else ""

            new_events.append({
                "date":  date_iso,
                "title": title,
                "where": where,
                "type":  etype,
                "link":  ev.get("localist_url") or ev.get("url") or ""
            })

        # Pagination
        pg = payload.get("page", {})
        current = int(pg.get("current", page))
        total   = int(pg.get("total", current))
        if current >= total:
            break
        page += 1

    merged = existing + new_events
    merged.sort(key=lambda e: e.get("date",""), reverse=True)

    with open(OUT, "w", encoding="utf-8") as f:
        json.dump(merged, f, indent=2, ensure_ascii=False)
    print(f"Window {start_str} + {days} days • Added {len(new_events)} RTG events; total now {len(merged)}")

if __name__ == "__main__":
    main()
