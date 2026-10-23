"""India-specific heuristics: vehicle registration (state/RTO), PIN codes,
STD / +91 phone codes, railway/highway/km-stone text, regional brands.

ALL OUTPUT IS HEURISTIC. Curated, partial tables; verify independently.
"""
from __future__ import annotations

import re

STATE_CODES = {
    "AN": "Andaman & Nicobar", "AP": "Andhra Pradesh", "AR": "Arunachal Pradesh", "AS": "Assam",
    "BR": "Bihar", "CG": "Chhattisgarh", "CH": "Chandigarh", "DD": "Dadra & Nagar Haveli and Daman & Diu",
    "DL": "Delhi", "GA": "Goa", "GJ": "Gujarat", "HP": "Himachal Pradesh", "HR": "Haryana",
    "JH": "Jharkhand", "JK": "Jammu & Kashmir", "KA": "Karnataka", "KL": "Kerala", "LA": "Ladakh",
    "LD": "Lakshadweep", "MH": "Maharashtra", "ML": "Meghalaya", "MN": "Manipur", "MP": "Madhya Pradesh",
    "MZ": "Mizoram", "NL": "Nagaland", "OD": "Odisha", "OR": "Odisha (old)", "PB": "Punjab",
    "PY": "Puducherry", "RJ": "Rajasthan", "SK": "Sikkim", "TN": "Tamil Nadu", "TR": "Tripura",
    "TS": "Telangana", "TG": "Telangana", "UK": "Uttarakhand", "UA": "Uttarakhand (old)",
    "UP": "Uttar Pradesh", "WB": "West Bengal", "BH": "Bharat series (not location-bound)",
}
# Maharashtra RTO codes (curated; heuristic)
MH_RTO = {
    "01": "Mumbai Central (Tardeo)", "02": "Mumbai West (Andheri)", "03": "Mumbai East (Worli)",
    "04": "Thane", "05": "Kalyan", "06": "Pen (Raigad)", "07": "Sindhudurg", "08": "Ratnagiri",
    "09": "Kolhapur", "10": "Sangli", "11": "Satara", "12": "Pune", "13": "Solapur",
    "14": "Pimpri-Chinchwad", "15": "Nashik", "16": "Ahmednagar", "17": "Shrirampur", "18": "Dhule",
    "19": "Jalgaon", "20": "Chh. Sambhajinagar (Aurangabad)", "21": "Jalna", "22": "Parbhani",
    "23": "Beed", "24": "Latur", "25": "Dharashiv (Osmanabad)", "26": "Nanded", "27": "Amravati",
    "28": "Buldhana", "29": "Yavatmal", "30": "Akola", "31": "Nagpur (Urban)", "32": "Wardha",
    "33": "Gadchiroli", "34": "Chandrapur", "35": "Gondia", "36": "Bhandara", "37": "Washim",
    "38": "Hingoli", "39": "Nandurbar", "40": "Nagpur (Rural)", "41": "Malegaon", "42": "Baramati",
    "43": "Navi Mumbai (Vashi)", "44": "Ambajogai", "45": "Akluj", "46": "Panvel", "47": "Borivali (Mumbai)",
    "48": "Vasai-Virar (Palghar district)", "49": "Nagpur (East)", "50": "Karad",
}
OTHER_RTO = {  # a few well-known non-MH examples
    ("GJ", "01"): "Ahmedabad", ("GJ", "05"): "Surat", ("GJ", "06"): "Vadodara", ("DL", "01"): "Delhi (North)",
    ("KA", "01"): "Bengaluru (Central)", ("TN", "01"): "Chennai (Central)", ("TS", "09"): "Hyderabad (Central)",
    ("DD", "03"): "Daman", ("WB", "01"): "Kolkata",
}
PLATE_RE = re.compile(r"\b([A-Z]{2})[\s\-\.]?(\d{1,2})[\s\-\.]?([A-Z]{0,3})[\s\-\.]?(\d{3,4})\b")
BH_RE = re.compile(r"\b(\d{2})[\s\-]?BH[\s\-]?(\d{4})[\s\-]?([A-Z]{1,2})\b")

PIN_ZONE = {"1": "North (Delhi, HR, PB, HP, J&K, CH)", "2": "North (UP, Uttarakhand)",
            "3": "West (Rajasthan, Gujarat, DD)", "4": "West (Maharashtra, MP, Goa, Chhattisgarh)",
            "5": "South (AP, Telangana, Karnataka)", "6": "South (Tamil Nadu, Kerala, Puducherry, Lakshadweep)",
            "7": "East (WB, Odisha, NE states, A&N)", "8": "East (Bihar, Jharkhand)", "9": "Army Postal Service"}
PIN_2 = {"11": "Delhi", "12": "Haryana", "13": "Haryana", "14": "Punjab", "15": "Punjab", "16": "Punjab/Chandigarh",
         "17": "Himachal Pradesh", "18": "Jammu & Kashmir", "19": "Jammu & Kashmir/Ladakh", "20": "Uttar Pradesh",
         "21": "Uttar Pradesh", "22": "Uttar Pradesh", "23": "Uttar Pradesh", "24": "Uttar Pradesh/Uttarakhand",
         "25": "Uttar Pradesh", "26": "Uttar Pradesh/Uttarakhand", "27": "Uttar Pradesh", "28": "Uttar Pradesh",
         "30": "Rajasthan", "31": "Rajasthan", "32": "Rajasthan", "33": "Rajasthan", "34": "Rajasthan",
         "36": "Gujarat", "37": "Gujarat", "38": "Gujarat", "39": "Gujarat", "40": "Maharashtra (Mumbai/Konkan/Goa)",
         "41": "Maharashtra (Pune/W. Maharashtra)", "42": "Maharashtra (N. Maharashtra)", "43": "Maharashtra (Marathwada)",
         "44": "Maharashtra (Vidarbha)", "45": "Madhya Pradesh", "46": "Madhya Pradesh", "47": "Madhya Pradesh",
         "48": "Madhya Pradesh", "49": "Chhattisgarh", "50": "Telangana", "51": "Andhra Pradesh", "52": "Andhra Pradesh",
         "53": "Andhra Pradesh", "56": "Karnataka", "57": "Karnataka", "58": "Karnataka", "59": "Karnataka",
         "60": "Tamil Nadu", "61": "Tamil Nadu", "62": "Tamil Nadu", "63": "Tamil Nadu", "64": "Tamil Nadu",
         "67": "Kerala", "68": "Kerala", "69": "Kerala", "70": "West Bengal", "71": "West Bengal", "72": "West Bengal",
         "73": "West Bengal/Sikkim", "74": "West Bengal/A&N", "75": "Odisha", "76": "Odisha", "77": "Odisha",
         "78": "Assam", "79": "North-East states", "80": "Bihar", "81": "Bihar/Jharkhand", "82": "Bihar/Jharkhand",
         "83": "Jharkhand", "84": "Bihar", "85": "Bihar/Jharkhand"}
PIN_3 = {"400": "Mumbai", "401": "Thane/Palghar district (Vasai-Virar, Mira-Bhayandar, Palghar)",
         "402": "Raigad", "403": "Goa", "410": "Raigad/Pune rural", "411": "Pune city", "412": "Pune district",
         "421": "Thane district (Kalyan, Bhiwandi, Ulhasnagar)", "440": "Nagpur", "422": "Nashik",
         "110": "Delhi", "560": "Bengaluru", "600": "Chennai", "500": "Hyderabad", "700": "Kolkata",
         "380": "Ahmedabad", "395": "Surat"}
PIN_RE = re.compile(r"(?<!\d)([1-9]\d{2})\s?(\d{3})(?!\d)")

STD = {"022": "Mumbai/Thane", "0250": "Vasai-Virar (Palghar district)", "02525": "Palghar",
       "020": "Pune", "011": "Delhi", "033": "Kolkata", "044": "Chennai", "080": "Bengaluru",
       "040": "Hyderabad", "079": "Ahmedabad", "0261": "Surat", "0265": "Vadodara", "0712": "Nagpur",
       "0253": "Nashik", "0251": "Kalyan/Dombivli", "0240": "Chh. Sambhajinagar", "0231": "Kolhapur",
       "0832": "Goa", "0141": "Jaipur", "0522": "Lucknow", "0484": "Kochi", "0471": "Thiruvananthapuram"}
PHONE_RE = re.compile(r"(?:\+?91[\s\-]?|0)?([6-9]\d{4}[\s\-]?\d{5})\b|(\(?0\d{2,4}\)?[\s\-]?\d{6,8})\b")

ROAD_PATTERNS = [
    (re.compile(r"\bN\.?H\.?[\s\-]?(\d{1,3}[A-Z]?)\b", re.I), "National Highway {0}"),
    (re.compile(r"\bS\.?H\.?[\s\-]?(\d{1,3})\b", re.I), "State Highway {0}"),
    (re.compile(r"\b([A-Z][A-Za-z]{2,})\s+(\d{1,4})\s?(?:km|KM|Km|कि\.?मी\.?)\b"), "km-stone / distance sign: {0} {1} km"),
    (re.compile(r"\b(?:Platform|प्लॅटफॉर्म|प्लेटफॉर्म)\s*(?:No\.?)?\s*(\d+)", re.I), "Railway platform {0}"),
    (re.compile(r"\b([A-Z][A-Z ]{2,})\s+(?:JN|JN\.|JUNCTION|RD|ROAD)\b"), "Railway station name board: {0}"),
    (re.compile(r"\b(?:Sea level|समुद्र सपाटी|समुद्र तल)\D{0,10}(\d+(?:\.\d+)?)", re.I), "Station elevation board: {0} m"),
]

BRANDS = {  # regional brand -> heuristic region. Curated & non-exhaustive.
    "aarey": "Mumbai (Maharashtra govt dairy)", "mahanand": "Maharashtra", "gokul": "Kolhapur, Maharashtra",
    "chitale": "Pune, Maharashtra", "best": "Mumbai (BEST buses)", "msrtc": "Maharashtra (state transport)",
    "vvmc": "Vasai-Virar Municipal Corporation", "bmc": "Mumbai (BMC)", "mbmc": "Mira-Bhayandar", "tmc": "Thane",
    "amul": "Gujarat origin, sold pan-India (weak hint)", "gsrtc": "Gujarat", "aavin": "Tamil Nadu",
    "nandini": "Karnataka", "milma": "Kerala", "vijaya": "Andhra Pradesh/Telangana", "verka": "Punjab",
    "sudha": "Bihar", "saras": "Rajasthan", "mother dairy": "Delhi NCR", "ksrtc": "Karnataka/Kerala",
    "tnstc": "Tamil Nadu", "apsrtc": "Andhra Pradesh", "tsrtc": "Telangana", "dtc": "Delhi",
    "kmc": "Kolkata", "ghmc": "Hyderabad", "bbmp": "Bengaluru",
}


def plates(text: str) -> list[dict]:
    out = []
    up = text.upper()
    for m in PLATE_RE.finditer(up):
        st, rto, series, num = m.groups()
        if st not in STATE_CODES or st == "BH":
            continue
        rto = rto.zfill(2)
        region = MH_RTO.get(rto) if st == "MH" else OTHER_RTO.get((st, rto))
        out.append({"plate": f"{st}-{rto}-{series}-{num}".replace("--", "-"), "state": STATE_CODES[st],
                    "rto": f"{st}-{rto}", "rto_region": region or "RTO not in curated table",
                    "confidence": 0.6 if region else 0.45})
    for m in BH_RE.finditer(up):
        out.append({"plate": m.group(0), "state": STATE_CODES["BH"], "rto": None,
                    "rto_region": "BH series: owner can be anywhere in India", "confidence": 0.1})
    return out


def pincodes(text: str) -> list[dict]:
    out = []
    for m in PIN_RE.finditer(text):
        pin = m.group(1) + m.group(2)
        reg = PIN_3.get(pin[:3]) or PIN_2.get(pin[:2])
        if not reg:
            continue
        out.append({"pin": pin, "zone": PIN_ZONE.get(pin[0]), "region": reg,
                    "precision": "3-digit sorting district" if pin[:3] in PIN_3 else "2-digit postal circle",
                    "confidence": 0.55 if pin[:3] in PIN_3 else 0.4})
    return out


def phones(text: str) -> list[dict]:
    out = []
    for m in PHONE_RE.finditer(text):
        if m.group(1):
            out.append({"number": m.group(0).strip(), "type": "mobile",
                        "region": "Indian mobile (+91); region NOT inferable (number portability)", "confidence": 0.1})
        elif m.group(2):
            digits = re.sub(r"\D", "", m.group(2))
            for L in (5, 4, 3):
                if digits[:L] in STD:
                    out.append({"number": m.group(2), "type": "landline", "std": digits[:L],
                                "region": STD[digits[:L]], "confidence": 0.5})
                    break
    return out


def road_rail(text: str) -> list[dict]:
    out = []
    for rx, tmpl in ROAD_PATTERNS:
        for m in rx.finditer(text):
            out.append({"match": m.group(0), "hint": tmpl.format(*[g.strip() for g in m.groups()]), "confidence": 0.35})
    return out


def brands(text: str) -> list[dict]:
    low = " " + re.sub(r"[^a-z ]", " ", text.lower()) + " "
    return [{"brand": b, "region": r, "confidence": 0.25, "heuristic": True}
            for b, r in BRANDS.items() if f" {b} " in low]


def _dedupe(items: list[dict], key: str) -> list[dict]:
    seen, out = set(), []
    for it in items:
        k = re.sub(r"[\s\-]", "", str(it.get(key))).upper()
        if k not in seen:
            seen.add(k)
            out.append(it)
    return out


def analyze(text: str) -> dict:
    return {"plates": _dedupe(plates(text), "plate"), "pincodes": _dedupe(pincodes(text), "pin"),
            "phones": _dedupe(phones(text), "number"), "road_rail": _dedupe(road_rail(text), "match"),
            "brands": brands(text),
            "disclaimer": "Heuristic, curated & partial tables. Treat as leads, not conclusions."}
