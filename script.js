fetch('https://api.yourdomain.com/endpoint-that-returns-js')
  .then(response => {
    if (!response.ok) {
      throw new Error('Network response was not ok');
    }
    return response.text();  // This assumes the response is plain text representing the script
  })
  .then(script => {
    // Create a new script element and set its content
    let scriptElement = document.createElement('script');
    scriptElement.textContent = script;

    // Append the script element to the document's head (or body)
    document.head.appendChild(scriptElement);

    // Optionally, remove the script element after appending
    document.head.removeChild(scriptElement);
  })
  .catch(error => {
    console.error('There was a problem with the fetch operation:', error);
  });
