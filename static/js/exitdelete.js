// // Get the current URL of the app
// const currentUrl = window.location.href;

// // Get the name of the database from the URL
// const urlParams = new URLSearchParams(window.location.search);
// const dbName = urlParams.get('db');

// // Listen for the beforeunload event to detect when the user leaves the app
// window.addEventListener('beforeunload', function (event) {
//   // Check if the user is leaving the app by checking if the current URL is the same as the app's homepage URL
//   if (window.location.href === currentUrl) {
//     // If the user is leaving the app, send a DELETE request to delete the database
//     const xhr = new XMLHttpRequest();
//     xhr.open('DELETE', `/delete-db?db=${deletedb}`, false);
//     xhr.send();
//   }
// });

// function sendDeleteRequest() {
//   const formData = new FormData();
//   formData.append('db_name', deletedb);

//   if (navigator.sendBeacon) {
//     navigator.sendBeacon(`/delete-db`, formData);
//   } else {
//     const xhr = new XMLHttpRequest();
//     xhr.open('POST', `/delete-db`, true);
//     xhr.send(formData);
//   }
// }

// window.addEventListener('beforeunload', sendDeleteRequest);
// window.addEventListener('unload', sendDeleteRequest);

// document.addEventListener('visibilitychange', function() {
//   if (document.visibilityState === 'hidden') {
//     sendDeleteRequest();
//   }
// });



// const xhr = new XMLHttpRequest();

// // Listen for the beforeunload event to detect when the user leaves the app
// window.addEventListener('beforeunload', function (event) {
//   // Check if the user is leaving the app by checking if the current URL is the same as the app's homepage URL
//   if (window.location.href === currentUrl) {
//     // If the user is leaving the app, send a DELETE request to delete the database
//     xhr.open('DELETE', `/delete-db/${deletedb}`, false);
//     xhr.send();
//   }
// });

// // Listen for the unload event to detect when the browser window is closed
// window.addEventListener('unload', function (event) {
//   // Send the DELETE request to delete the database
//   xhr.open('DELETE', `/delete-db/${deletedb}`, false);
//   xhr.send();
// });

// console.log(`Sending DELETE request to /delete-db/${deletedb}`);

// const xhr = new XMLHttpRequest();
// xhr.open('DELETE', `/delete-db/${deletedb}`, false);
// xhr.send();

// console.log('DELETE request sent');