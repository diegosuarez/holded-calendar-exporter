# Requirements are covered with `pip install google-api-python-client google-auth icalendar beautifulsoup4 requests jq`
import json, re, jq, requests, hashlib, uuid, sys
from datetime import datetime, timedelta
from bs4 import BeautifulSoup
from googleapiclient.discovery import build
from googleapiclient.errors import HttpError
from icalendar import Calendar, Event
from google.oauth2 import service_account
import os.path

TOKEN_URL = "https://app.holded.com/internal/auth/get-token?origin=holded"
LOGIN_URL = "https://app.holded.com/login/"
CALENDAR_URL = "https://app.holded.com/teamzone/calendar"
TWO_FACTOR_URL = "https://app.holded.com/internal/auth/two-factor-confirm"
EMPLOYEES_URL = "https://api.holded.com/api/team/v1/employees"
SCOPES = ['https://www.googleapis.com/auth/calendar']

#Custom vars to be set by the user.
COMPANY_SELECTION_URL =  "" # "https://app.holded.com/accounts/xxxxxxxxxxxxxxxxxxx"
GOOGLE_CREDENTIALS_FILE = "" # Fichero de credenciales de Google "/home/pepito/credentials.json"
CALENDAR_NAME = 'Vacaciones'  # Nombre del calendario donde vamos a subir 
DOMAIN = "" # midominio.com
EMAIL = "diegosuarez@"+DOMAIN
HOLDED_PASSWORD = "12345678" # Password de holded
HOLDED_ADMIN_KEY = "123456789abcdef" #API key de la cuenta de administrador de holded

def get_calendar_data(month, year):
    session = requests.Session()
    session.headers.update({'User-Agent': 'Mozilla/5.0 (X11; Linux x86_64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/99.0.4844.84 Safari/537.36'})
    login_data = {"email": EMAIL, "pass": HOLDED_PASSWORD, "platform": "web"}
    r = session.post(TOKEN_URL, login_data)
    code_2fa = input("Enter the 2FA code sent to your email\n")
    session.post(TWO_FACTOR_URL, {"platform": "web", "email": EMAIL, "code": code_2fa})
    r = session.post(TOKEN_URL, login_data)
    token = r.json()['token']
    session.get(LOGIN_URL + token)
    session.get(COMPANY_SELECTION_URL)
    calendar_data = f"month={month}&year={year}&filters%5Bname%5D=&filters%5Bworkplace%5D=all&filters%5Bteam%5D=all&filters%5Bsupervised%5D=0"
    r = session.post(CALENDAR_URL, calendar_data)
    return r.json()

def get_employees():
    """
    Fetch employee and vacation data from the Holded platform.
    """
    headers = {
        "accept": "application/json",
        "key": HOLDED_ADMIN_KEY
    }

    try:
        response = requests.get(EMPLOYEES_URL, headers=headers)
        response.raise_for_status()
        data = response.json()

        # jq filter to retrieve active employees
        jq_filter = '.employees[] | select( (.terminated==null))'
        active_employees = jq.compile(jq_filter).input(data).all()

        return active_employees

    except requests.exceptions.RequestException as e:
        print(f"Error making API request: {e}")
        return None
    except json.JSONDecodeError as e:
        print(f"Error decoding JSON response: {e}")
        return None
    except Exception as e:
        print(f"Error executing jq query: {e}")
        return None

def create_ics_from_holded_data(data, file_name="vacations.ics"):
    """
    Create an ICS file with vacation data extracted from a JSON file,
    extracting the 'timesoff' variable from a script in the HTML.
    """
    html_content = data.get("html", "")
    soup = BeautifulSoup(html_content, 'html.parser')

    # Extract the script containing the 'timesoff' variable
    scripts = soup.find_all('script')
    timesoff_script = None
    for script in scripts:
        if script.string and "var timesoff" in script.string:
            timesoff_script = script.string
            break

    if not timesoff_script:
        print("Error: Script with 'timesoff' variable not found.")
        return

    # Extract the JSON from 'timesoff' using a regular expression
    match = re.search(r"var timesoff = ({.*?});", timesoff_script)
    if not match:
        print("Error: Could not extract JSON from 'timesoff'.")
        return

    timesoff_json_str = match.group(1)

    try:
        timesoff = json.loads(timesoff_json_str)
    except json.JSONDecodeError as e:
        print(f"Error decoding 'timesoff' JSON: {e}")
        return

    # Process and create the ICS file
    with open(file_name, 'w') as f:
        f.write("BEGIN:VCALENDAR\n")
        f.write("VERSION:2.0\n")
        f.write("PRODID:-//HoldedSync//Vacations//EN\n")

        employees = get_employees()

        for employee_id, timeoffs_list in timesoff['list'].items():
            if not employee_id.startswith("employee#"):
                continue  # Skip keys that are not employees

            for timeoff in timeoffs_list:
                date_str = timeoff["date"]
                month_str = timeoff["month"]
                year_str = timeoff["year"]
                timeoff_type = timeoff["timeofftype"]
                employee_id_clean = employee_id.split("#")[1]  # Extract employee ID
                name = jq.compile(' .[] | select(.id == "' + employee_id_clean + '" ) | (.name + " " + .lastName)').input(employees).first()
                try:
                    # Format the date
                    date_str = f"{date_str.zfill(2)}/{month_str.zfill(2)}/{year_str}"
                    start_dt = datetime.strptime(date_str, "%d/%m/%Y")
                    end_dt = start_dt  # Assume end date is the same as start date
                except ValueError:
                    print(f"Error processing date: {date_str}. Skipping this event.")
                    continue

                # Generate a unique UID for the event
                m = hashlib.md5()
                m.update(f"#{name}#{date_str}#{timeoff_type}".encode('utf-8'))
                uid = uuid.UUID(m.hexdigest())
                f.write("BEGIN:VEVENT\n")
                f.write(f"UID:{uid}@{DOMAIN}\n")
                f.write(f"SUMMARY:{name} - {timeoff_type}\n")

                # Format dates for ICS
                f.write(f"DTSTART;VALUE=DATE:{start_dt.strftime('%Y%m%d')}\n")
                f.write(f"DTEND;VALUE=DATE:{(end_dt + timedelta(days=1)).strftime('%Y%m%d')}\n")  # Add 1 day to the end

                f.write("END:VEVENT\n")

        f.write("END:VCALENDAR\n")

def import_ics_to_calendar(ics_file_path, calendar_name):
    """Import events from an ICS file to a specific Google Calendar."""
    creds = service_account.Credentials.from_service_account_file(GOOGLE_CREDENTIALS_FILE, scopes=SCOPES)
    creds = creds.with_subject(EMAIL)
    try:
        service = build('calendar', 'v3', credentials=creds)

        # Find the ID of the "Vacations" calendar
        calendar_id = find_calendar_id(service, calendar_name)
        if not calendar_id:
            print(f'Calendar "{calendar_name}" not found.')
            return

        with open(ics_file_path, 'rb') as f:
            calendar_data = Calendar.from_ical(f.read())

        for component in calendar_data.walk():
            if isinstance(component, Event):
                uid = str(component.get('uid'))
                if event_exists(service, calendar_id, uid):
                    print(f'Event with UID "{uid}" already exists. Skipping.')
                    continue
                event = {
                    'summary': str(component.get('summary')),
                    'start': {
                        'date': component.get('dtstart').dt.isoformat(),
                        'timeZone': 'Europe/Madrid',  # Example timezone.
                    },
                    'end': {
                        'date': component.get('dtend').dt.isoformat(),
                        'timeZone': 'Europe/Madrid',
                    },
                    'iCalUID': uid,
                    'extendedProperties.private': "uid=" + component.get('uid'),
                }

                event = service.events().insert(calendarId=calendar_id, body=event).execute()
                print(f'Event created: {event.get("htmlLink")}')

    except HttpError as error:
        print(f'An error occurred: {error}')

def find_calendar_id(service, calendar_name):
    """Find and return the ID of a calendar by its name."""
    page_token = None
    while True:
        calendar_list = service.calendarList().list(pageToken=page_token).execute()
        for calendar_list_entry in calendar_list['items']:
            if calendar_list_entry['summary'] == calendar_name:
                return calendar_list_entry['id']
        page_token = calendar_list.get('nextPageToken')
        if not page_token:
            break
    return None

def event_exists(service, calendar_id, uid):
    """Check if an event with the given UID exists in the calendar."""
    try:
        events = service.events().list(
            calendarId=calendar_id,
            iCalUID=uid,
        ).execute()
        return len(events['items']) > 0
    except HttpError as error:
        print(f'An error occurred while checking event existence: {error}')
        return False

if __name__ == "__main__":
    if len(sys.argv) != 3:
        print("Usage: python sync-calendar.py <month> <year>")
        sys.exit(1)

    try:
        month = int(sys.argv[1])
        year = int(sys.argv[2])
    except ValueError:
        print("Error: Month and year must be integers.")
        sys.exit(1)

    if month < 1 or month > 12:
        print("Error: Month must be between 1 and 12.")
        sys.exit(1)

    data = get_calendar_data(month, year)
    create_ics_from_holded_data(data)
    import_ics_to_calendar('vacations.ics', CALENDAR_NAME)
