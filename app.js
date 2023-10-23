const express = require('express');
const axios = require('axios');
const path = require('path');

const app = express();

// Set the view engine to pug
app.set('view engine', 'pug');
app.set('views', path.join(__dirname, 'views'));

// Route that fetches the JSON data from an API and renders it with a Pug template
app.get('/', async (req, res) => {
    try {
        // Replace with your API endpoint
        const apiUrl = 'https://api.example.com/data';
        const response = await axios.get(apiUrl);

        // The data from the API
        const data = response.data;

        // Render your pug template with the data
        res.render('index', { data });
    } catch (error) {
        console.error('Error fetching data: ', error);
        res.status(500).send('Error fetching data from the API');
    }
});

const PORT = process.env.PORT || 3000;
app.listen(PORT, () => console.log(`Server is running on port ${PORT}`));
