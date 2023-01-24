# Endpoints
## /post/admin/new
Call it with post to create a new admin.
returns the admin uuid
    var requestOptions = {
    method: 'POST',
    redirect: 'follow'
    };

    fetch("localhost:5050/post/admin/new", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /get/admins
Return list of admins and their uuids
    var requestOptions = {
    method: 'GET',
    redirect: 'follow'
    };

    fetch("localhost:5050/get/admins", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /get/drivers
Returns all drivers and the uuid of the admin they are assigned to
    var requestOptions = {
    method: 'GET',
    redirect: 'follow'
    };

    fetch("localhost:5050/get/drivers", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /get/admin/drivers
Returns all the drivers assigned to an admin
Provide admin_id
    var raw = "";

    var requestOptions = {
    method: 'GET',
    body: raw,
    redirect: 'follow'
    };

    fetch("localhost:5050/get/admin/drivers?admin_id=2", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /get/admin/output
Returns the output map for a driver
Provide admin_id
    var requestOptions = {
    method: 'GET',
    redirect: 'follow'
    };

    fetch("localhost:5050/get/admin/output?admin_id=2", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /get/admin/dynamicpoints
Returns the dynamic points added by an admin
Provide admin_id
    var requestOptions = {
    method: 'GET',
    redirect: 'follow'
    };

    fetch("localhost:5050/get/admin/dynamicpoints?admin_id=2", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /post/admin/dynamicpoint
Allows admin to add a dynamic point
Provide a json in the format {"admin_id" : ... , "data" : {"address" : ..., ...}} in the request body
    var myHeaders = new Headers();
    myHeaders.append("Content-Type", "application/json");

    var raw = JSON.stringify({
    "admin_id": 2,
    "data": {
        "address": "1260, SY 35/4, SJR Tower's, 7th Phase, 24th Main, Puttanhalli, JP Nagar, Bangalore"
    }
    });

    var requestOptions = {
    method: 'POST',
    headers: myHeaders,
    body: raw,
    redirect: 'follow'
    };

    fetch("localhost:5050/post/admin/dynamicpoint", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

## /post/admin/input
Reads input map in the form xlsx, xls, csv and assigns required number of drivers to the admin
Provide admin_id, no of drivers and input file in form data
    var formdata = new FormData();
    formdata.append("file", fileInput.files[0], "bangalore_pickups.xlsx");
    formdata.append("no_of_drivers", "5");
    formdata.append("admin_id", "2");

    var requestOptions = {
    method: 'POST',
    body: formdata,
    redirect: 'follow'
    };

    fetch("localhost:5050/post/admin/input", requestOptions)
    .then(response => response.text())
    .then(result => console.log(result))
    .catch(error => console.log('error', error));

 
