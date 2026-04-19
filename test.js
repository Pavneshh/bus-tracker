const http = require('http');

const data = JSON.stringify({ lat: 20.383275, lng: 72.930816 });

const options = {
  hostname: '127.0.0.1',
  port: 5000,
  path: '/api/buses/VISHWAKARMA%20TRAVELS/location',
  method: 'POST',
  headers: {
    'Content-Type': 'application/json',
    'Content-Length': data.length
  }
};

const req = http.request(options, (res) => {
  let responseData = '';
  res.on('data', (chunk) => { responseData += chunk; });
  res.on('end', () => { console.log(responseData); });
});

req.write(data);
req.end();