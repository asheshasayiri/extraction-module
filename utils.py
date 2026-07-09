# utils.py
def validate_fields(data):
    required_fields = ["name", "roll_no", "course", "specialization",
                       "division", "cgpa", "institution", "graduation_year"]
    filled = sum(1 for f in required_fields if data.get(f))
    return round((filled / len(required_fields)) * 100, 2)