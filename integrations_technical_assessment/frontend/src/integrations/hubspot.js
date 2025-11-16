

import { useState } from 'react';
import {
    Box,
    Button,
    CircularProgress
} from '@mui/material';
import axios from 'axios';

export const HubspotIntegration = ({ user, org, integrationParams, setIntegrationParams }) => {
    const [isConnected, setIsConnected] = useState(false);
    const [isConnecting, setIsConnecting] = useState(false);

    const handleConnectClick = async () => {
        setIsConnecting(true);
        try {
            const form = new FormData();
            form.append("user_id", user);
            form.append("org_id", org);

            const resp = await axios.post(
                "http://localhost:8000/integrations/hubspot/authorize",
                form
            );

            const authUrl =
                typeof resp.data === "string"
                    ? resp.data
                    : resp.data.auth_url;

            window.open(
                authUrl,
                "hubspot_oauth",
                "width=600,height=700,left=200,top=100"
            );

        } catch (err) {
            console.error("Failed to start HubSpot OAuth", err);
        } finally {
            setIsConnecting(false);
        }
    };

    const handleRetrieveCredentials = async () => {
        setIsConnecting(true);
        try {
            const form = new FormData();
            form.append("user_id", user);
            form.append("org_id", org);

            const resp = await axios.post(
                "http://localhost:8000/integrations/hubspot/credentials",
                form
            );

            setIntegrationParams({
                ...integrationParams,
                credentials: resp.data,
                type: "HubSpot"
            });

            setIsConnected(true);
        } catch (err) {
            console.error("No HubSpot credentials found yet:", err);
        } finally {
            setIsConnecting(false);
        }
    };

    return (
        <Box sx={{ display: 'flex', alignItems: 'center', gap: 2 }}>
            <Button
                variant="contained"
                onClick={handleConnectClick}
                disabled={isConnecting || isConnected}
            >
                {isConnected
                    ? "HubSpot Connected"
                    : isConnecting
                        ? <CircularProgress size={20} />
                        : "Connect to HubSpot"}
            </Button>

            <Button
                variant="outlined"
                onClick={handleRetrieveCredentials}
                disabled={isConnecting}
            >
                {isConnecting ? <CircularProgress size={20} /> : "Retrieve HubSpot Credentials"}
            </Button>
        </Box>
    );
};
