import { useState } from 'react';
import {
    Box,
    TextField,
    Button,
} from '@mui/material';
import axios from 'axios';

const endpointMapping = {
    notion: 'notion',
    airtable: 'airtable',
    hubspot: 'hubspot',
};

export const DataForm = ({ integrationType, credentials }) => {
    const [loadedData, setLoadedData] = useState(null);
    const endpoint = endpointMapping[integrationType?.toLowerCase()];
    const handleLoad = async () => {
        if (!integrationType || !credentials) {
            alert('Integration type or credentials missing!');
            return;
        }
        console.log('Integration:', integrationType);
        console.log('Endpoint:', endpoint);
        console.log('Credentials:', credentials);

        try {
            const formData = new FormData();
            formData.append('credentials', JSON.stringify(credentials));

            const response = await axios.post(
                `http://localhost:8000/integrations/${endpoint}/load`,
                formData
            );

            setLoadedData(response.data);
        } catch (e) {
            alert(e?.response?.data?.detail);
        }
    };

    return (
        <Box display='flex' justifyContent='center' alignItems='center' flexDirection='column' width='100%'>
            <Box display='flex' flexDirection='column' width='100%'>
                <TextField
                    label="Loaded Data"
                    value={loadedData || ''}
                    sx={{ mt: 2 }}
                    InputLabelProps={{ shrink: true }}
                    disabled
                />
                <Button onClick={handleLoad} sx={{ mt: 2 }} variant='contained'>
                    Load Data
                </Button>
                <Button onClick={() => setLoadedData(null)} sx={{ mt: 1 }} variant='contained'>
                    Clear Data
                </Button>
            </Box>
        </Box>
    );
};
