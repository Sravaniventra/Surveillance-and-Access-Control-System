/* =====================================================
   NAVIGATION
===================================================== */

const pages = document.querySelectorAll(".page");

const tabs = document.querySelectorAll(".top-tab");


function openPage(pageName) {

    pages.forEach(page => {

        page.classList.remove("active-page");

    });


    const target = document.getElementById(pageName);

    if (target) {

        target.classList.add("active-page");

    }


    tabs.forEach(tab => {

        tab.classList.remove("active");

        if (tab.dataset.page === pageName) {

            tab.classList.add("active");

        }

    });

}


/* TOP TABS */

tabs.forEach(tab => {

    tab.addEventListener("click", () => {

        openPage(tab.dataset.page);

    });

});


/* QUICK ACTIONS */

document.querySelectorAll("[data-page-target]")
    .forEach(button => {

        button.addEventListener("click", () => {

            openPage(button.dataset.pageTarget);

        });

    });



/* =====================================================
   CAMERA LOCATIONS
===================================================== */

const locations =
    document.querySelectorAll(".location");

const miniCameras =
    document.querySelectorAll(".mini-camera");


locations.forEach((location, index) => {

    location.addEventListener("click", () => {

        locations.forEach(item => {

            item.classList.remove("active");

        });

        location.classList.add("active");


        miniCameras.forEach(camera => {

            camera.classList.remove("selected");

        });


        if (miniCameras[index]) {

            miniCameras[index]
                .classList.add("selected");

        }

    });

});



/* =====================================================
   MINI CAMERA SELECTION
===================================================== */

miniCameras.forEach((camera, index) => {

    camera.addEventListener("click", () => {

        miniCameras.forEach(item => {

            item.classList.remove("selected");

        });

        camera.classList.add("selected");


        locations.forEach(item => {

            item.classList.remove("active");

        });


        if (locations[index]) {

            locations[index]
                .classList.add("active");

        }

    });

});



/* =====================================================
   CLOCK
===================================================== */

function updateClock() {

    const now = new Date();


    let hours = now.getHours();

    const minutes =
        String(now.getMinutes()).padStart(2, "0");

    const seconds =
        String(now.getSeconds()).padStart(2, "0");


    const ampm =
        hours >= 12 ? "PM" : "AM";


    hours = hours % 12;

    hours = hours || 12;


    const time =
        `${String(hours).padStart(2,"0")}:${minutes}:${seconds}`;


    const fullTime =
        `${String(hours).padStart(2,"0")}:${minutes}:${seconds} ${ampm}`;


    const topClock =
        document.getElementById("topClock");


    const commandClock =
        document.getElementById("commandClock");


    if (topClock) {

        topClock.textContent = time;

    }


    if (commandClock) {

        commandClock.textContent = fullTime;

    }


    /* DATE */

    const months = [

        "JAN",
        "FEB",
        "MAR",
        "APR",
        "MAY",
        "JUN",
        "JUL",
        "AUG",
        "SEP",
        "OCT",
        "NOV",
        "DEC"

    ];


    const dateText =
        `${String(now.getDate()).padStart(2,"0")}
        ${months[now.getMonth()]}
        ${now.getFullYear()}`;


    const dateElement =
        document.getElementById("fullDate");


    if (dateElement) {

        dateElement.textContent =
            dateText;

    }

}


updateClock();

setInterval(updateClock, 1000);



/* =====================================================
   FACE IMAGE UPLOAD
===================================================== */

const imageInput =
    document.getElementById("imageInput");


if (imageInput) {

    imageInput.addEventListener(
        "change",
        function(event) {

            const file =
                event.target.files[0];


            if (!file) {

                return;

            }


            const image =
                document.getElementById(
                    "uploadedImage"
                );


            const uploadContent =
                document.querySelector(
                    ".upload-content"
                );


            const faceBox =
                document.getElementById(
                    "faceBox"
                );


            const reader =
                new FileReader();


            reader.onload = function(e) {

                image.src =
                    e.target.result;


                image.style.display =
                    "block";


                uploadContent.style.display =
                    "none";


                faceBox.style.display =
                    "none";

            };


            reader.readAsDataURL(file);


            updateRecognitionTime();

        }

    );

}



/* =====================================================
   DEMO FACE RECOGNITION
===================================================== */

const processButton =
    document.getElementById(
        "processButton"
    );


if (processButton) {

    processButton.addEventListener(
        "click",
        function() {

            const image =
                document.getElementById(
                    "uploadedImage"
                );


            if (
                !image.src ||
                image.style.display === "none"
            ) {

                alert(
                    "Please upload a surveillance image first."
                );

                return;

            }


            const result =
                document.getElementById(
                    "recognitionResult"
                );


            const access =
                document.getElementById(
                    "accessResult"
                );


            const circle =
                document.getElementById(
                    "statusCircle"
                );


            result.textContent =
                "ANALYZING";


            access.textContent =
                "Deep learning model processing image";


            circle.className =
                "status-circle";


            circle.innerHTML =
                '<i class="fa-solid fa-spinner fa-spin"></i>';


            processButton.disabled =
                true;


            setTimeout(() => {


                /*
                 * TEMPORARY DEMO RESULT
                 *
                 * This will later be replaced
                 * with your Python ML backend.
                 */


                const authorized =
                    Math.random() > 0.35;


                const faceBox =
                    document.getElementById(
                        "faceBox"
                    );


                if (authorized) {


                    result.textContent =
                        "MATCH FOUND";


                    access.textContent =
                        "Access Granted";


                    circle.className =
                        "status-circle success";


                    circle.innerHTML =
                        '<i class="fa-solid fa-check"></i>';


                    document.getElementById(
                        "employeeId"
                    ).textContent =
                        "EMP-1027";


                    document.getElementById(
                        "employeeName"
                    ).textContent =
                        "Registered Employee";


                    document.getElementById(
                        "department"
                    ).textContent =
                        "Engineering";


                    document.getElementById(
                        "designation"
                    ).textContent =
                        "Software Engineer";


                    document.getElementById(
                        "accessLevel"
                    ).textContent =
                        "Level 2";


                    faceBox.style.display =
                        "block";


                    faceBox.style.borderColor =
                        "#42d96b";


                } else {


                    result.textContent =
                        "UNKNOWN PERSON";


                    access.textContent =
                        "Access Denied";


                    circle.className =
                        "status-circle denied";


                    circle.innerHTML =
                        '<i class="fa-solid fa-xmark"></i>';


                    document.getElementById(
                        "employeeId"
                    ).textContent =
                        "UNKNOWN";


                    document.getElementById(
                        "employeeName"
                    ).textContent =
                        "Unknown Person";


                    document.getElementById(
                        "department"
                    ).textContent =
                        "---";


                    document.getElementById(
                        "designation"
                    ).textContent =
                        "---";


                    document.getElementById(
                        "accessLevel"
                    ).textContent =
                        "No Access";


                    faceBox.style.display =
                        "block";


                    faceBox.style.borderColor =
                        "#ff4d4d";

                }


                updateRecognitionTime();


                processButton.disabled =
                    false;


            }, 1600);

        }

    );

}



/* =====================================================
   RECOGNITION TIME
===================================================== */

function updateRecognitionTime() {

    const element =
        document.getElementById(
            "recognitionTime"
        );


    const timestamp =
        document.getElementById(
            "timestamp"
        );


    if (!element && !timestamp) {

        return;

    }


    const now = new Date();


    let hours =
        now.getHours();


    const minutes =
        String(now.getMinutes())
            .padStart(2, "0");


    const seconds =
        String(now.getSeconds())
            .padStart(2, "0");


    const ampm =
        hours >= 12 ? "PM" : "AM";


    hours =
        hours % 12 || 12;


    const formatted =
        `${String(now.getDate()).padStart(2,"0")}-${String(now.getMonth()+1).padStart(2,"0")}-${now.getFullYear()} ${hours}:${minutes}:${seconds} ${ampm}`;


    if (element) {

        element.textContent =
            formatted;

    }


    if (timestamp) {

        timestamp.textContent =
            formatted;

    }

}


setInterval(
    updateRecognitionTime,
    1000
);