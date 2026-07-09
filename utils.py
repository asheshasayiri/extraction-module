def validate_fields(data):

    score = 0
    total = 7

    if data.get("name"): score += 1
    if data.get("roll_no"): score += 1
    if data.get("course"): score += 1
    if data.get("specialization"): score += 1
    if data.get("cgpa"): score += 1
    if data.get("institution"): score += 1
    if data.get("graduation_year"): score += 1

    return round((score / total) * 100, 2)