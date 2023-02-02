import requests, re
from datetime import datetime
from pathlib import Path

class TenttiArkisto:
    def __init__(self, base_url: str, todo_path: str, done_path: str) -> None:
        self.base_url = base_url if base_url.endswith("/") else base_url + "/"
        self.todo_path = todo_path
        self.done_path = done_path
        self.client = requests.session()
        self.courses: dict = {}
        self.languages: dict[str, str] = {}

    '''
    Find all PDF files and create an exam object from each of them.
    '''
    def findFiles(self) -> list[dict]:
        files = []
        for path in Path(self.todo_path).glob("*.pdf"):
            course, date_str, description = path.stem.split("_")
            if description in ["tentamen", "sluttentamen"] or "mellanförhör" in description or "deltentamen" in description:
                language = "swedish"
            elif description == "exam" or "midterm" in description:
                language = "english"
            elif description == "tentti" or "välikoe" in description:
                language = "finnish"
            else:
                raise Exception(f"Invalid description in file {path}")

            try:
                date = datetime.strptime(date_str, "%Y%m%d")
            except ValueError:
                raise Exception(f"Invalid description in file {path}")

            files.append({
                "course": self.courses[course],
                "exam_date": date.strftime("%Y-%m-%d"),
                "desc": description.replace("-", " ").capitalize(),
                "lang": self.languages[language],
                "path": path,
            })

        print(f"Found {len(files)} files")

        return files

    '''
    Fetch the mappings between course_codes <-> course_id and language <-> language_id. Duplicate course codes can exists, but a certain id can be forced with the method argument.
    '''
    def fetchOptions(self, course_overrides = {}) -> None:
        r = self.client.get(self.base_url + "exams/add/")

        self.courses = {}
        matches = re.findall('<option value="(\d*)">(.+): .*</option>', r.text)
        for id, corse_code in matches:
            c = corse_code.lower()

            if c in course_overrides:
                self.courses[c] = course_overrides[c]
                continue

            if c not in self.courses:
                self.courses[c] = id
                continue

            print(f"Unhandled duplicate course found: {corse_code} ({self.courses[c]} and {id})")

        self.languages = {}
        # XXX: Finds more than just the languages, but I can not be bothered to fix it.
        matches = re.findall('<option value="(\d)">(.+)</option>', r.text)
        for id, language in matches:
            l = language.lower()
            if l in self.languages:
                raise Exception(f"Duplicate language found: {language}")
            self.languages[l] = id

        print(f"Found {len(self.courses)} courses")
        print(f"Found {len(self.languages)} languages")

    '''
    Sign in to tenttiarkisto.
    '''
    def login(self, username, password):
        URL = self.base_url + "login/"
        token = self.getCSRFToken(URL)

        r = self.client.post(URL, data={
            "csrfmiddlewaretoken": token,
            "username": username,
            "password": password,
        }, headers={
            "Referer": URL,
            "Content-Type": "application/x-www-form-urlencoded",
        })

        if r.status_code == 200 and "sessionid" in self.client.cookies:
            print(f"Logged in successfully as {username}")
        else:
            raise Exception("Failed to log in")

    def getCSRFToken(self, url) -> str:
        r = self.client.get(url)
        matches = re.findall('name="csrfmiddlewaretoken" value="([a-zA-Z0-9]*)"', r.text)
        return matches[0]

    '''
    Start the process of adding all exams to tenttiarkisto. Specify the optional argument if you want to restrict the amount of exams, for testing purposes for example.
    '''
    def addAllExams(self, n = None) -> None:
        URL = self.base_url + "exams/add/"
        FILES = self.findFiles()

        if not len(self.courses):
            self.fetchOptions()

        token = None
        for i, exam in enumerate(FILES):
            if n != None and i >= n:
                print("skipping", exam)
                continue

            print(exam)

            if not token:
                token = self.getCSRFToken(URL)
            ok, token = self.__addExam(exam, token)

            p = exam["path"]
            if ok:
                p.rename(f"{self.done_path}/{p.stem}.pdf")
            else:
                raise Exception("Failed to add exam {p}")

    def __addExam(self, exam: dict, token: str):
        URL = self.base_url + "exams/add/"

        r = self.client.post(URL, data={
            "csrfmiddlewaretoken": token,
            "course": exam["course"],
            "exam_date": exam["exam_date"],
            "desc": exam["desc"],
            "lang": exam["lang"],
        }, files={
            "exam_file": exam["path"].open("rb"),
        }, headers={
            "Referer": URL,
        })

        matches = re.findall('name="csrfmiddlewaretoken" value="([a-zA-Z0-9]*)"', r.text)
        token = matches[0]

        return r.status_code == 200, token


if __name__ == "__main__":
    URL = ""
    USERNAME = ""
    PASSWORD = ""


    if not URL:
        raise Exception("Give a valid URL to tenttiarkisto")

    ta = TenttiArkisto(URL, "./todo", "./done")

    if USERNAME and PASSWORD:
        ta.login(USERNAME, PASSWORD)

    ta.fetchOptions({
        "ms-a0102": "2253",
        "ene-59.4101": "1960",
        "kul-49.3400": "1375",
        "mec-e1020": "3860",
        "mec-e4001": "3631",
        "ms-a0102": "2253",
        "ms-a0503": "2068",
        "phys-c0220": "2441",
        "s-17.3020": "1400",
        "tfy-0.3252": "735",
    })
    ta.addAllExams()
