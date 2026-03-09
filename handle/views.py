from django.shortcuts import render
from .serializers import CodeExecuteSerializer,TC,ChatbotSerializer,VisSer,HanSer
import requests
from rest_framework.views import APIView
from rest_framework.response import Response
from rest_framework import status
from .tracer import run_and_trace
from collections import defaultdict
import math
from django.conf import settings

class ExecuteCodeAPIView(APIView):
    def post(self, request):
        serializer = CodeExecuteSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        language = serializer.validated_data['language'].lower()
        code = serializer.validated_data['code']
        test_cases = serializer.validated_data['testCases']
        payload = {
            "language": language,
            "code": code,
            "testCases": test_cases
        }
        try:
            response = requests.post(
                settings.COMPILER_URL,
                json=payload,
                headers={"Content-Type": "application/json"},
                timeout=15
            )
            
            return Response(response.json(), status=response.status_code)

        except requests.exceptions.RequestException as e:
            return Response(
                {"success": False, "message": f"External API Error: {str(e)}"}, 
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

class FTC(APIView):
    def post(self, request):
        serializer = TC(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        code = serializer.validated_data['code']
        prompt = (
            "Analyze the time complexity of the following code. "
            "Output ONLY the Big O notation (e.g., O(n), O(log n)). "
            "Do not explain.\n\n"
            f"{code}"
        )
        
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )
        payload = {
            "contents": [
                {
                    "parts": [{"text": prompt}]
                }
            ]
        }
        headers = {
            "Content-Type": "application/json"
        }
        try:
            response = requests.post(url, json=payload, headers=headers)
            return Response(response.json(), status=response.status_code)
        except requests.exceptions.RequestException as e:
            return Response({"error": str(e)}, status=500)
        

class CB(APIView):
    def post(self, request):
        serializer = ChatbotSerializer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors, status=400)

        v = serializer.validated_data
        history_str = "\n".join(
            f"{m['sender']}: {m['content']}" for m in v.get("history", [])[-5:]
        )
        prompt = (
            "Be polite and humble. Your name is Jarvis.\n"
            "Only ans coding related doubts ,or basic doubts like your name , you can see code etc and greetings if msg is not related  to these topics  politely tell them you are code helper or something like that"
            "if user paste code ans in respect of it default code is right below"
            f"Context Code: {v.get('code','')}\n"
            f"Recent History: {history_str}\n"
            f"User says: {v.get('currentMsg','')}"
        )
        url = (
            "https://generativelanguage.googleapis.com/v1beta/models/"
            "gemini-2.5-flash:generateContent"
            f"?key={settings.GEMINI_API_KEY}"
        )

        payload = {
            "contents": [
                {
                    "role": "user",
                    "parts": [{"text": prompt}]
                }
            ]
        }
        response = requests.post(url, json=payload)
        res_data = response.json()
        if response.status_code != 200 or "candidates" not in res_data:
            return Response(
                {"error": "Gemini failed", "response": res_data},
                status=500
            )

        reply = res_data["candidates"][0]["content"]["parts"][0]["text"]
        return Response({"reply": reply})


class Visual(APIView):
    def post(self, request):
        serializer = VisSer(data=request.data)
        if not serializer.is_valid():
            return Response(serializer.errors,status=status.HTTP_400_BAD_REQUEST)
        data = serializer.validated_data
        code = data.get("code")
        user_input = data.get("input", "")
        try:
            steps = run_and_trace(code, user_input)
            return Response(
                {
                    "success": True,
                    "steps": steps
                },
                status=status.HTTP_200_OK
            )
        except Exception as e:
            return Response(
                {"success": False, "error": str(e)},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )


class Han(APIView):
    def get(self, request):
        serializer = HanSer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        userId = serializer.validated_data["userId"]
        try:
            response = requests.get(
                f"{settings.CODEFORCES_USER_INFO}?handles={userId}",
                timeout=5
            )
            return Response(response.json(), status=response.status_code)

        except requests.exceptions.RequestException:
            return Response(
                {"error": "Failed to connect to Codeforces"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        



VERDICT_MAP = {
    "OK": "OK",
    "WRONG_ANSWER": "WRONG_ANSWER",
    "TIME_LIMIT_EXCEEDED": "TLE",
    "MEMORY_LIMIT_EXCEEDED": "MLE",
}

def clean_submissions(submissions):
    def problem_template():
        return {
            "rating": None,
            "tags": [],
            "accepted": False,
            "counts": defaultdict(int)
        }

    problems = defaultdict(problem_template)

    for sub in submissions:
        p = sub["problem"]
        key = f"{p['contestId']}-{p['index']}"

        if problems[key]["rating"] is None:
            problems[key]["rating"] = p.get("rating")
            problems[key]["tags"] = p.get("tags", [])

        verdict = sub["verdict"]
        normalized = VERDICT_MAP.get(verdict, "OTHER")
        problems[key]["counts"][normalized] += 1

        if verdict == "OK":
            problems[key]["accepted"] = True

    final_output = {}
    for k, v in problems.items():
        v["counts"] = dict(v["counts"])
        final_output[k] = v

    return final_output



def derive_stats(cleaned_data):
    rating_count = defaultdict(int)
    verdict_count = defaultdict(int)
    tag_stats = defaultdict(lambda: {
        "attempted": 0,
        "solved": 0,
        "submissions": 0
    })

    for problem in cleaned_data.values():
        rating = problem["rating"]
        tags = problem["tags"]
        counts = problem["counts"]
        accepted = problem["accepted"]

        total_submissions = sum(counts.values())

        if accepted and rating is not None:
            rating_count[str(rating)] += 1

        for verdict, cnt in counts.items():
            verdict_count[verdict] += cnt
        for tag in tags:
            tag_stats[tag]["attempted"] += 1
            tag_stats[tag]["submissions"] += total_submissions
            if accepted:
                tag_stats[tag]["solved"] += 1

    return {
        "rating_bucket": dict(rating_count),
        "verdicts": dict(verdict_count),
        "tag_stats": dict(tag_stats)
    }

class Subinfo(APIView):
    def get(self, request):
        serializer = HanSer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        userId = serializer.validated_data["userId"]
        try:
            response = requests.get(
                f"{settings.CODEFORCES_USER_STATUS}?handle={userId}",
                timeout=10
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] != "OK":
                return Response(
                    {"error": "Codeforces API returned error"},
                    status=status.HTTP_502_BAD_GATEWAY
                )
            cleaned_data = clean_submissions(data["result"])
            derived_data=derive_stats(cleaned_data)
            return Response(derived_data, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException:
            return Response(
                {"error": "Failed to connect to Codeforces"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )
        

def compute_iqr(ranks):
    sorted_ranks = sorted(ranks)
    n = len(sorted_ranks)

    q1 = sorted_ranks[n // 4]
    q3 = sorted_ranks[(3 * n) // 4]

    return q3 - q1

def recent(ranks, deltas):
    k = min(5, len(ranks))
    if k == 0:
        return None
    recent_ranks = ranks[-k:]
    recent_deltas = deltas[-k:]
    total = k
    best_rank = min(recent_ranks)
    worst_rank = max(recent_ranks)
    avg_rank = sum(recent_ranks) // total
    avg_delta = sum(recent_deltas) / total
    iqr = compute_iqr(recent_ranks)
    iqr_ratio = round(iqr / avg_rank, 3) if avg_rank > 0 else 0
    positive_cnt = sum(1 for d in recent_deltas if d > 0)
    positive_ratio = round((positive_cnt / total) * 100, 1)
    longest_streak = 0
    current = 0
    for d in recent_deltas:
        if d > 0:
            current += 1
            longest_streak = max(longest_streak, current)
        else:
            current = 0

    mean_rank = sum(recent_ranks) / total
    variance = sum((r - mean_rank) ** 2 for r in recent_ranks) / total
    rank_std_dev = int(math.sqrt(variance))

    return {
        "window": f"last_{k}",
        "total_contests": k,
        "best_rank": best_rank,
        "worst_rank": worst_rank,
        "avg_rank": avg_rank,
        "avg_delta": round(avg_delta, 1),
        "positive_ratio": positive_ratio,
        "longest_streak": longest_streak,
        "rank_stability": rank_std_dev,
        "iqr_ratio": iqr_ratio
    }

def derive_contest_analytics(contests):
    if not contests:
        return []
    graph_data = []
    total = len(contests)
    ranks = []
    deltas = []
    for c in contests:
        ranks.append(c["rank"])
        deltas.append(c["newRating"] - c["oldRating"])
        graph_data.append({
            "contestName": c.get("contestName", ""),
            "time": c["ratingUpdateTimeSeconds"],
            "rating": c["newRating"],
            "delta": deltas[-1],
            "rank": c["rank"],
        })

    best_rank = min(ranks)
    worst_rank = max(ranks)
    avg_rank = sum(ranks) // total
    avg_delta = sum(deltas) / total
    iqr = compute_iqr(ranks)
    iqr_ratio = round(iqr / avg_rank, 3) if avg_rank > 0 else 0
    positive_cnt = sum(1 for d in deltas if d > 0)
    positive_ratio = round((positive_cnt / total) * 100, 1)
    longest_streak = 0
    current = 0
    for d in deltas:
        if d > 0:
            current += 1
            longest_streak = max(longest_streak, current)
        else:
            current = 0

    mean_rank = sum(ranks) / total
    variance = sum((r - mean_rank) ** 2 for r in ranks) / total
    rank_std_dev = int(math.sqrt(variance))
    lifetime = {
        "window": "lifetime",
        "total_contests": total,
        "best_rank": best_rank,
        "worst_rank": worst_rank,
        "avg_rank": avg_rank,
        "avg_delta": round(avg_delta, 1),
        "positive_ratio": positive_ratio,
        "longest_streak": longest_streak,
        "rank_stability": rank_std_dev,
        "iqr_ratio": iqr_ratio,
        "graphData": graph_data
    }
    recent_stats = recent(ranks, deltas)
    return [lifetime, recent_stats]


class Contestinfo(APIView):
    def get(self,request):
        serializer=HanSer(data=request.query_params)
        if not serializer.is_valid():
            return Response(serializer.errors, status=status.HTTP_400_BAD_REQUEST)
        userId = serializer.validated_data["userId"]
        try:
            response = requests.get(
                f"{settings.CODEFORCES_USER_RATING}?handle={userId}",
                timeout=5
            )
            response.raise_for_status()
            data = response.json()
            if data["status"] != "OK":
                return Response(
                    {"error": "Codeforces API returned error"},
                    status=status.HTTP_502_BAD_GATEWAY
                )
            derived_data=derive_contest_analytics(data["result"])
            return Response(derived_data, status=status.HTTP_200_OK)
        except requests.exceptions.RequestException:
            return Response(
                {"error": "Failed to connect to Codeforces"},
                status=status.HTTP_500_INTERNAL_SERVER_ERROR
            )

