"""Cell-aware edge service migration -- Decision Engine.

Subscribes to data-session events from a 5G core, maps the reported gNB to an
edge site, and asks the service orchestrator to move the edge application to
that site when the UE has handed over.

All deployment-specific values (orchestrator credentials, the gNB-to-edge
table, the SUPI under observation) come from the environment or from a
topology file -- see config.py and topology.example.yaml.
"""

import datetime
import json
import logging
import signal
import sys
import threading
import time

import requests
from flask import Flask, jsonify, request

from config import load_settings, load_topology

app = Flask(__name__)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)

settings = load_settings()
telco_infra = load_topology()

# Dictionary to store the previous event data
previous_event = {}
# List to store all received events
event_log = []
# Number of inter-gNB handovers observed for the SUPI under test
handover_count = 0


def save_migration_time(migration_time):
    """Append one migration measurement to the results file."""
    with open(settings.migration_log_path, "a") as file:
        json.dump(migration_time, file)
        file.write("\n")


class OrchestratorClient:
    """Northbound-interface client for the service orchestrator.

    Authenticates against the orchestrator's Ory Kratos endpoint and carries
    the resulting session token on subsequent NBI requests, refreshing it
    whenever the orchestrator answers 401.
    """

    def __init__(self, user_email, password, org, base_host):
        self.user_email = user_email
        self.password = password
        self.org = org
        self.base_host = base_host

        self.kratos_public = f"https://{base_host}/.ory/kratos/public"
        self.base_url = f"https://{base_host}/nbi-api/"
        self.session_token = None

    def fetch_action_url(self) -> str:
        response = requests.get(
            f"{self.kratos_public}/self-service/login/api",
            headers={"Accept": "application/json"},
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        return response.json().get("ui", {}).get("action")

    def fetch_token(self, action_url: str) -> str:
        login_payload = {
            "identifier": self.user_email,
            "password": self.password,
            "method": "password",
            "org": self.org,
        }
        response = requests.post(
            action_url,
            json=login_payload,
            headers={"Content-Type": "application/json"},
            timeout=settings.request_timeout,
        )
        response.raise_for_status()
        self.session_token = response.json().get("session_token")
        return self.session_token

    def reauthenticate(self):
        action_url = self.fetch_action_url()
        self.session_token = self.fetch_token(action_url)
        logger.info("Re-authenticated with the orchestrator")

    def make_authenticated_request(self, method: str, endpoint: str, data: dict = None) -> dict:
        if not self.session_token:
            self.reauthenticate()

        headers = {
            "Authorization": f"Bearer {self.session_token}",
            "x-org": self.org,
            "Content-Type": "application/json",
        }
        url = f"{self.base_url}{endpoint}"
        response = requests.request(
            method, url, headers=headers, json=data, timeout=settings.request_timeout
        )

        if response.status_code == 401:
            logger.info("Request rejected with 401 - re-authenticating")
            self.reauthenticate()
            headers["Authorization"] = f"Bearer {self.session_token}"
            response = requests.request(
                method, url, headers=headers, json=data, timeout=settings.request_timeout
            )

        response.raise_for_status()
        return response.json()


orchestrator = OrchestratorClient(
    user_email=settings.orchestrator_user,
    password=settings.orchestrator_password,
    org=settings.orchestrator_org,
    base_host=settings.orchestrator_host,
)


def log_telco_infra():
    logger.info("Telco infrastructure mapping:")
    for edge, info in telco_infra.items():
        logger.info(
            f"{edge}: UPF={info['upf']}, gNB ID={info['gnb_id']}, "
            f"TAI={info['tai']}, Site ID={info['site_id']}"
        )


def handle_sigterm(signum, frame):
    logger.info("Received SIGTERM. Performing cleanup...")
    logger.info("Cleanup completed. Exiting...")
    sys.stdout.flush()
    sys.stderr.flush()
    sys.exit(0)


signal.signal(signal.SIGTERM, handle_sigterm)


def process_event(event):
    global previous_event, handover_count
    logger.info("Processing event...")

    add_text_data = json.loads(event.get("add_text", "{}"))

    # Only events for the subscriber under observation trigger orchestration
    if str(add_text_data.get("supi")) != str(settings.supi_of_interest):
        logger.info(
            f"Received event for SUPI {add_text_data.get('supi')}. "
            "No orchestration action triggered."
        )
        return

    current_gnb_id = add_text_data.get("gnb_id")
    previous_gnb_id = previous_event.get("gnb_id") if previous_event else None

    logger.info(f"Current gNB ID: {current_gnb_id}, Previous gNB ID: {previous_gnb_id}")

    if previous_gnb_id is not None and previous_gnb_id != current_gnb_id:
        handover_count += 1
        logger.info(f"Handover detected. Total handovers: {handover_count}")

    perform_action(add_text_data)

    previous_event = {"gnb_id": current_gnb_id}


@app.route("/form", methods=["POST"])
def receive_event():
    event = request.form.to_dict()
    logger.info("--------------- Received an event from the 5G core ---------------")

    for key, value in event.items():
        logger.info(f"{key}: {value}")

    event_log.append(event)

    threading.Thread(target=process_event, args=(event,)).start()

    return "Event received successfully", 200


@app.route("/", methods=["GET"])
def welcome():
    return (
        """
    <h1>Welcome to the 5G core event subscriber server!</h1>
    <p>Available endpoints:</p>
    <ul>
        <li>GET / - Welcome message and list of endpoints</li>
        <li>GET /health - Health status</li>
        <li>POST /form - Receive event data</li>
        <li>GET /events - View received events</li>
        <li>GET /telco_infra - View telco infrastructure mapping</li>
        <li>GET /handover_count - View handover count</li>
    </ul>
    """,
        200,
    )


@app.route("/health", methods=["GET"])
def health():
    return jsonify(status="UP"), 200


@app.route("/events", methods=["GET"])
def get_events():
    logger.info(f"Retrieved {len(event_log)} events.")
    return jsonify(event_log), 200


@app.route("/telco_infra", methods=["GET"])
def get_telco_infra():
    log_telco_infra()
    return jsonify(telco_infra), 200


@app.route("/handover_count", methods=["GET"])
def get_handover_count():
    return jsonify(handover_count=handover_count), 200


def perform_action(event):
    logger.info("***** Performing action based on the received event. *****")

    gnb_id = event.get("gnb_id")

    for edge, info in telco_infra.items():
        # gNB IDs arrive as JSON numbers from some cores and as strings from
        # others, so compare them as strings.
        if str(info["gnb_id"]) != str(gnb_id):
            continue

        logger.info(
            f"UE is now connected to gNB ID {gnb_id}, mapped to {edge} "
            f"with UPF {info['upf']}, TAI {info['tai']}, Site ID {info['site_id']}"
        )

        services = orchestrator.make_authenticated_request("GET", "services")

        service_name = settings.service_name
        service = next((s for s in services if s["serviceChain"]["name"] == service_name), None)
        if not service:
            logger.info(f"SERVICE NOT FOUND: the service {service_name} was not found.")
            return

        # The orchestrator stores the chart values as a YAML blob; the site
        # label inside it is what pins the workload to an edge node.
        chart_values = service["serviceChain"]["blocks"][0]["blockchartValues"]
        site_id = chart_values.split("site:\n    label: ")[1].split("\n")[0]
        logger.info(f"Service {service_name} is currently running on site {site_id}")

        new_site_id = info["site_id"]
        if site_id == new_site_id:
            logger.info(
                f"Service {service_name} already runs on the correct site "
                f"{new_site_id}. No update required."
            )
            return

        logger.info(f"Migration required: updating service {service_name} to site {new_site_id}")
        updated_chart_values = chart_values.replace(site_id, new_site_id)

        # The application keeps its state in a Redis instance local to the
        # edge node, so the endpoint has to follow the workload.
        if "REDIS_HOST: " in chart_values:
            current_redis_host = chart_values.split("REDIS_HOST: ")[1].split("\n")[0].strip()
            redis_host = info["redis_host"]
            logger.info(f"Current REDIS_HOST: {current_redis_host}, new REDIS_HOST: {redis_host}")
            updated_chart_values = updated_chart_values.replace(
                f"REDIS_HOST: {current_redis_host}", f"REDIS_HOST: {redis_host}"
            )
        else:
            logger.warning("REDIS_HOST key not found in the chart values")

        service["serviceChain"]["blocks"][0]["blockchartValues"] = updated_chart_values

        block = service["serviceChain"]["blocks"][0]
        update_payload = {
            "id": service["serviceChain"]["id"],
            "name": service["serviceChain"]["name"],
            "blocks": [
                {
                    "id": block["id"],
                    "displayName": block["displayName"],
                    "blockChartName": block["blockchartName"],
                    "blockChartVersion": block["blockchartVersion"],
                    "values": updated_chart_values,
                }
            ],
        }

        start_time = datetime.datetime.now()

        service_id = service["serviceChain"]["id"]
        orchestrator.make_authenticated_request(
            "PUT", f"services/{service_id}", data=update_payload
        )
        logger.info("Service migration started...")

        # Poll until the orchestrator reports the service back in sync; that
        # transition is what we measure as the service migration time.
        deadline = time.monotonic() + settings.migration_timeout
        end_time = None
        while time.monotonic() < deadline:
            status_response = orchestrator.make_authenticated_request(
                "GET", f"services/{service_id}"
            )
            if status_response["serviceChain"]["status"] == settings.in_sync_status:
                end_time = datetime.datetime.now()
                break
            time.sleep(settings.poll_interval)

        if end_time is None:
            logger.error(
                f"Service {service_id} did not reach {settings.in_sync_status} "
                f"within {settings.migration_timeout}s"
            )
            return

        migration_time = (end_time - start_time).total_seconds()

        save_migration_time(
            {
                "service_id": service_id,
                "start_time": start_time.isoformat(),
                "end_time": end_time.isoformat(),
                "migration_time_seconds": migration_time,
            }
        )

        logger.info(f"Service migrated. Service migration time: {migration_time} seconds")
        return


if __name__ == "__main__":
    logger.info("Starting the 5G core event subscriber server...")
    log_telco_infra()
    orchestrator.reauthenticate()
    try:
        app.run(host="0.0.0.0", port=settings.listen_port)
    except Exception as e:
        logger.error(f"An error occurred while running the server: {e}")
    finally:
        logger.info("Server has been shut down.")
        sys.stdout.flush()
