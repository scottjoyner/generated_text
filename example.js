const axios = require('axios');

// Save endpoint
axios.post('http://localhost:5000/save', {
  filename: 'data.json',
  data: {
    x: [1, 2, 3],
    y: [4, 5, 6],
  },
})
  .then((response) => {
    console.log(response.data.message);
  })
  .catch((error) => {
    console.error(error);
  });

// View Graph endpoint
axios.get('http://localhost:5000/view-graph/data.json')
  .then((response) => {
    console.log(response.data);
  })
  .catch((error) => {
    console.error(error.response.data);
  });
