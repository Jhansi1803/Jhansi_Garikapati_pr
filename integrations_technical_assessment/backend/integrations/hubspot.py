# slack.py

import json
import secrets
import base64
from fastapi import Request, HTTPException
from fastapi.responses import HTMLResponse
import httpx
import asyncio
from integrations.integration_item import IntegrationItem

from redis_client import add_key_value_redis, get_value_redis, delete_key_redis

CLIENT_ID = 'c1cfcfc4-f3c2-42d6-ba99-e36a9eb48227'
CLIENT_SECRET = '1cb30003-8e40-4004-b850-afbbd0264da0'
REDIRECT_URI = 'http://localhost:8000/integrations/hubspot/oauth2callback'

authorization_url = 'https://app.hubspot.com/oauth/authorize'
token_url = 'https://api.hubapi.com/oauth/v1/token'

async def authorize_hubspot(user_id, org_id):
    """
    Build HubSpot OAuth authorization URL, save state to redis, and return the URL.
    """
    state = secrets.token_urlsafe(16)
    state_data = {"state": state, "user_id": user_id, "org_id": org_id}
    encoded_state = base64.urlsafe_b64encode(json.dumps(state_data).encode()).decode()

    scopes = "crm.objects.contacts.read"
    auth_url = (
        f"{authorization_url}?client_id={CLIENT_ID}"
        f"&redirect_uri={REDIRECT_URI}"
        f"&scope={scopes}"
        f"&state={encoded_state}"
    )

    await add_key_value_redis(f"hubspot_state:{org_id}:{user_id}", json.dumps(state_data), expire=600)
    return auth_url


async def oauth2callback_hubspot(request: Request):
    
    if request.query_params.get("error"):
        raise HTTPException(status_code=400, detail=request.query_params.get("error_description"))

    code = request.query_params.get("code")
    encoded_state = request.query_params.get("state")
    if not code or not encoded_state:
        raise HTTPException(status_code=400, detail="Missing code or state")

    state_data = json.loads(base64.urlsafe_b64decode(encoded_state).decode())
    original_state = state_data.get("state")
    user_id = state_data.get("user_id")
    org_id = state_data.get("org_id")

    saved_state = await get_value_redis(f"hubspot_state:{org_id}:{user_id}")
    if not saved_state or original_state != json.loads(saved_state).get("state"):
        raise HTTPException(status_code=400, detail="State does not match.")

    async with httpx.AsyncClient() as client:
        resp = await client.post(
            token_url,
            data={
                "grant_type": "authorization_code",
                "client_id": CLIENT_ID,
                "client_secret": CLIENT_SECRET,
                "redirect_uri": REDIRECT_URI,
                "code": code,
            },
            headers={"Content-Type": "application/x-www-form-urlencoded"},
            timeout=10,
        )

    if resp.status_code != 200:
        raise HTTPException(status_code=400, detail=f"Failed to exchange code: {resp.text}")

    await delete_key_redis(f"hubspot_state:{org_id}:{user_id}")
    await add_key_value_redis(f"hubspot_credentials:{org_id}:{user_id}", json.dumps(resp.json()), expire=600)

    close_window_script = """
    <html>
        <script>
            window.close();
        </script>
    </html>
    """
    return HTMLResponse(content=close_window_script)


async def get_hubspot_credentials(user_id, org_id):
    """
    Retrieve stored credentials from redis (set by oauth2callback), then delete them.
    Mirrors the behavior of other integrations.
    """
    credentials = await get_value_redis(f"hubspot_credentials:{org_id}:{user_id}")
    if not credentials:
        raise HTTPException(status_code=400, detail="No credentials found.")
    credentials = json.loads(credentials)
    await delete_key_redis(f"hubspot_credentials:{org_id}:{user_id}")
    return credentials


def create_integration_item_metadata_object(response_json: dict, item_type: str) -> IntegrationItem:
    """
    Create IntegrationItem from HubSpot object JSON.
    We attach a `parameters` attribute (list of dicts) to the IntegrationItem to match other integrations' behavior.
    """
    props = response_json.get("properties", {}) or {}
    
    if item_type == "contact":
        firstname = props.get("firstname")
        lastname = props.get("lastname")
        email = props.get("email")
        name = " ".join([x for x in [firstname, lastname] if x]) or email or response_json.get("id")
        iid = f"{response_json.get('id')}_Contact"
    elif item_type == "company":
        name = props.get("name") or props.get("domain") or response_json.get("id")
        iid = f"{response_json.get('id')}_Company"
    elif item_type == "deal":
        name = props.get("dealname") or response_json.get("id")
        iid = f"{response_json.get('id')}_Deal"
    else:
        name = response_json.get("id")
        iid = response_json.get("id")

    parameters = [{"name": k, "value": v} for k, v in props.items()]

    integration_item = IntegrationItem(
        id=iid,
        name=name,
        type=item_type,
        directory=False,
        url=None,
        children=None,
    )
    
    integration_item.parameters = parameters
    integration_item.raw = response_json
    return integration_item


async def get_items_hubspot(credentials) -> list[IntegrationItem]:
    """
    Fetch a set of HubSpot objects (contacts, companies, deals) using the supplied credentials JSON string.
    Return a list of IntegrationItem objects (like other integrations).
    """
    credentials = json.loads(credentials)
    access_token = credentials.get("access_token")
    if not access_token:
        return []

    headers = {"Authorization": f"Bearer {access_token}", "Content-Type": "application/json"}

    list_of_integration_item_metadata = []

    def _fetch(endpoint: str, params: dict | None = None):
        import requests

        url = f"https://api.hubapi.com{endpoint}"
        r = requests.get(url, headers=headers, params=params, timeout=10)
        if r.status_code == 200:
            return r.json()
        else:
            
            return None

   
    try:
        contacts_resp = _fetch("/crm/v3/objects/contacts", params={"limit": 20, "properties": "email,firstname,lastname,phone"})
        if contacts_resp and contacts_resp.get("results"):
            for c in contacts_resp.get("results", []):
                list_of_integration_item_metadata.append(create_integration_item_metadata_object(c, "contact"))
    except Exception as e:
        
        print("Error fetching HubSpot contacts:", e)

    try:
        companies_resp = _fetch("/crm/v3/objects/companies", params={"limit": 20, "properties": "name,domain,phone"})
        if companies_resp and companies_resp.get("results"):
            for c in companies_resp.get("results", []):
                list_of_integration_item_metadata.append(create_integration_item_metadata_object(c, "company"))
    except Exception as e:
        print("Error fetching HubSpot companies:", e)

    try:
        deals_resp = _fetch("/crm/v3/objects/deals", params={"limit": 20, "properties": "dealname,amount,dealstage"})
        if deals_resp and deals_resp.get("results"):
            for d in deals_resp.get("results", []):
                list_of_integration_item_metadata.append(create_integration_item_metadata_object(d, "deal"))
    except Exception as e:
        print("Error fetching HubSpot deals:", e)

    print(f"list_of_integration_item_metadata: {list_of_integration_item_metadata}")
    return list_of_integration_item_metadata
