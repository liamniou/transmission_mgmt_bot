import json
import httpx
import os
import retrying

from retrying import retry


# Terraform cloud
WORKSPACE_ID = os.getenv("WORKSPACE_ID")
WORKSPACE_NAME = os.getenv("WORKSPACE_NAME")
ORGANIZATION_NAME = os.getenv("ORGANIZATION_NAME")
TF_CLOUD_TOKEN = os.getenv("TF_CLOUD_TOKEN")

# Transmission
TRANSMISSION_PORT = os.getenv("TRANSMISSION_PORT", 9091)

# Other
GET_HOST_IP_RETRIES = 2
CHECK_TRANSMISSION_CONNECTION_RETRIES = 60


def check_latest_run():
    with httpx.Client() as client:
        headers = {
            "Authorization": f"Bearer {TF_CLOUD_TOKEN}",
            "Content-Type": "application/vnd.api+json",
        }
        r = client.get(
            f"https://app.terraform.io/api/v2/workspaces/{WORKSPACE_ID}/runs",
            headers=headers,
        )
    is_destroy = json.loads(r.text)["data"][0]["attributes"]["is-destroy"]
    status = json.loads(r.text)["data"][0]["attributes"]["status"]
    print(f'"is_destroy": {is_destroy}, "status": {status}')
    return {"is_destroy": is_destroy, "status": status}


def trigger_terraform(is_destroy, run_title):
    payload = {
        "data": {
            "attributes": {"is-destroy": is_destroy, "message": run_title},
            "type": "runs",
            "relationships": {
                "workspace": {"data": {"type": "workspaces", "id": WORKSPACE_ID}}
            },
        }
    }

    with httpx.Client() as client:
        headers = {
            "Authorization": "Bearer " + TF_CLOUD_TOKEN,
            "Content-Type": "application/vnd.api+json",
        }
        r = client.post(
            "https://app.terraform.io/api/v2/runs", headers=headers, json=payload
        )
        print(r)


def get_latest_wsout_id():
    with httpx.Client() as client:
        headers = {
            "Authorization": f"Bearer {TF_CLOUD_TOKEN}",
            "Content-Type": "application/vnd.api+json",
        }
        r = client.get(
            f"https://app.terraform.io/api/v2/state-versions?filter%5Bworkspace%5D%5Bname%5D={WORKSPACE_NAME}&filter%5Borganization%5D%5Bname%5D={ORGANIZATION_NAME}",
            headers=headers,
        )
        return json.loads(r.text)["data"][0]["relationships"]["outputs"]["data"][0][
            "id"
        ]


def get_host_ip_from_outputs(wsout_id):
    with httpx.Client() as client:
        headers = {
            "Authorization": f"Bearer {TF_CLOUD_TOKEN}",
            "Content-Type": "application/vnd.api+json",
        }
        r = client.get(
            f"https://app.terraform.io/api/v2/state-version-outputs/{wsout_id}",
            headers=headers,
        )
        return json.loads(r.text)["data"]["attributes"]


def retry_if_result_none(result):
    """Return True if we should retry (in this case when result is None), False otherwise"""
    return result is None


def wait(attempts, delay):
    print(
        f"Attempt {attempts}/{GET_HOST_IP_RETRIES}, retrying in {delay // 1000} seconds"
    )
    trigger_terraform("true", "Destroy from bot on timeout")
    return delay


@retry(
    retry_on_result=retry_if_result_none, wait_fixed=10000, stop_max_attempt_number=50
)
def get_transmission_ip_from_tf_output():
    latest_run = check_latest_run()
    if latest_run["status"] not in ["applied", "planned_and_finished"]:
        print("Latest run is not yet applied...")
        return None
    if latest_run["is_destroy"]:
        print("Latest run is destroy, triggering new run..")
        trigger_terraform("false", "Create from bot")
        return None
    return get_host_ip_from_outputs(get_latest_wsout_id())["value"]


@retry(
    retry_on_result=retry_if_result_none,
    wait_fixed=2000,
    stop_max_attempt_number=CHECK_TRANSMISSION_CONNECTION_RETRIES,
)
def check_transmission_connection(transmission_host, transmission_port):
    try:
        print(f"Trying to connect to {transmission_host}:{transmission_port}")
        httpx.get(f"http://{transmission_host}:{transmission_port}", timeout=10.0)
        return True
    except httpx.ConnectTimeout:
        print("ConnectionTimeout")
        return None


@retry(
    retry_on_result=retry_if_result_none,
    wait_func=wait,
    stop_max_attempt_number=GET_HOST_IP_RETRIES,
)
def get_ip_of_running_transmission():
    host_ip = get_transmission_ip_from_tf_output()
    print(f"Terraform IP output found: {host_ip}")
    try:
        check_transmission_connection(host_ip, TRANSMISSION_PORT)
        print(f"Successfully connected to {host_ip}")
        return host_ip
    except retrying.RetryError:
        print(f"Can't connect to {host_ip}, triggering terraform destroy")
        trigger_terraform("true", "Destroy from bot")
        return None
