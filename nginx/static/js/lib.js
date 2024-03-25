// toggle buttons based on checkboxes for rows
$(document).on('change', '.tr-checkbox', function () {
    var checkedCount = $('.tr-checkbox:checked').length;
    // Then, enable the correct buttons based on the status
    if (checkedCount > 0) {
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
    } else {
        // If no checkboxes are checked, disable all buttons
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
    }
});

function getInfo(containerId) {
    fetch('/actions/info/' + containerId)
        .then(response => response.json())
        .then(data => {
            // Create a new Blob from the JSON string
            var blob = new Blob([JSON.stringify(data, null, 2)], { type: 'application/json' });

            // Create an object URL from the Blob
            var url = URL.createObjectURL(blob);

            // Open the URL in a new tab
            window.open(url, '_blank');
        });
}

function getStats(containerId) {
    window.open('/actions/stats/' + containerId, '_blank');
}

$(document).ready(function () {

    $("#spinner").hide();
    $("#loading").show();

    // AJAX in the blocks
    // $("#primary-block").load("./static/pages/containers.html");

    // Get event sources
    var homepageSource = new EventSource('http://localhost:5002/api/streams/containerlist');
    var messagesSource = new EventSource('http://localhost:5002/api/streams/servermessages');

    // Function to close EventSource connections
    // close() calls the call_on_close in server and unsubscribes from topic
    function closeEventSources() {
        homepageSource.close();
        messagesSource.close();
    }

    // Close connections when the page is refreshed or closed
    $(window).on('beforeunload', function () {
        closeEventSources();
    });

    var tbody = $("table tbody");
    var previousState = {};
    homepageSource.onmessage = function (event) {
        var data = JSON.parse(event.data);
        $.each(data, function (i, container) {
            var tr = tbody.find('#row-' + container.ID);
            if (!tr.length) {
                // If the row does not exist, create it
                tr = $("<tr>").attr('id', 'row-' + container.ID);
                tr.append($("<td>").html('<input type="checkbox" class="tr-checkbox" value="' + container.ID + '" name="container"> <span class="spinner-grow spinner-grow-sm row-spinner d-none" role="status" aria-hidden="true"></span>'));
                tr.append($("<td>").attr('id', 'name-' + container.ID));
                tr.append($("<td>").attr('id', 'id-' + container.ID));
                tr.append($("<td>").attr('id', 'state-' + container.ID));
                tr.append($("<td>").attr('id', 'status-' + container.ID));
                tr.append($("<td>").attr('id', 'image-' + container.ID));
                tr.append($("<td>").attr('id', 'port-' + container.ID));
                tr.append($("<td>").html('<button class="transparent-btn" onclick="getInfo(\'' + container.ID + '\')"><i class="bi bi-info-circle text-primary"></i></button>' + '<button class="transparent-btn" onclick="getStats(\'' + container.ID + '\')"><i class="bi bi-bar-chart-fill text-primary"></i></button>'));
                tbody.append(tr);
            }

            // Update the cells with the new data only if it has changed
            if (previousState[container.ID]?.Names[0] !== container.Names[0]) {
                $('#name-' + container.ID).text(container.Names[0].substring(1));
            }
            if (previousState[container.ID]?.ID !== container.ID) {
                $('#id-' + container.ID).text(container.ID.substring(0, 12));
            }
            if (previousState[container.ID]?.State !== container.State) {
                $('#state-' + container.ID).html('<span class="badge bg-' + getStatusClass(container.State) + '">' + container.State + '</span>');
            }
            if (previousState[container.ID]?.Status !== container.Status) {
                $('#status-' + container.ID).html('<span class="badge bg-' + getStatusClass(container.Status) + '">' + container.Status + '</span>');
            }
            if (previousState[container.ID]?.Image !== container.Image) {
                $('#image-' + container.ID).text(container.Image);
            }
            if (previousState[container.ID]?.Ports !== container.Ports) {
                $('#port-' + container.ID).html(getPortBindings(container.Ports));
            }

            // Store the current state of the container for the next update
            previousState[container.ID] = container;
        });

        $("#loading").hide();
    };

    messagesSource.onmessage = function (event) {
        var data = JSON.parse(event.data);
        $('#message-container').append(
            '<div class="alert alert-' + data.category + ' alert-dismissible fade show" role="alert">' +
            data.text +
            '<button type="button" class="btn-close" data-bs-dismiss="alert" aria-label="Close"></button>' +
            '</div>'
        );
    };

    // handle prune check box
    $('#btncheck1').change(function () {
        $('#confirm-prune').toggleClass('disabled');
    });

    // handle prune button click
    $('#confirm-prune').on('click', function () {
        // hide prune modal
        $("#pruneModal").modal('hide');
        // uncheck box for next opening of modal
        $("#btncheck1").prop('checked', false);
        $("#confirm-prune").toggleClass('disabled');
        $.ajax({
            url: 'https://localhost:5001/api/system/prune',
            method: 'POST',
            success: function (result) {
            },
            error: function (result) {
                console.error(result);
            }
        })
    })

    // handle select all checkbox change
    $('#select-all').change(function () {
        // select all checkboxes with class of tr-checkbox and make them selected
        $('.tr-checkbox').prop('checked', this.checked);
        // enable/disable buttons
        if (this.checked) {
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
        } else {
            // If no checkboxes are checked, disable all buttons
            $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
        }
    });
});

function getStatusClass(status) {
    switch (status) {
        case "running": return "success";
        case "paused": return "warning";
        case "exited": return "danger";
        default: return "secondary";
    }
}

function getPortBindings(portBindings) {
    var result = "";
    $.each(portBindings, function (i, port) {
        if (port.PublicPort) {
            result += '<a href="http://localhost:' + port.PublicPort + '" target="_blank">' + port.PrivatePort + ':' + port.PublicPort + ' <i class="bi bi-box-arrow-up-right"></i></a> ';
        }
    });
    return result;
}

function performAction(action, actionBtnId) {
    // get all container ids that are checked
    var checkedIds = $('.tr-checkbox:checked').map(function () {
        return this.value;
    }).get();

    // diable action button based on actionText
    $('#' + actionBtnId).prop('disabled', true);

    // for each checked row, show the spinner and display the action text
    $('.tr-checkbox:checked').each(function () {
        // disable checkbox
        $(this).hide();
        var row = $(this).closest('tr');
        row.find('.row-spinner').toggleClass('d-none');
    });

    $.ajax({
        url: 'http://localhost:5002/api/containers/' + action,
        type: 'POST',
        contentType: 'application/json',
        data: JSON.stringify({ 'ids': checkedIds }),
        success: function (result) {
            // hide spinners
            $('.tr-checkbox:checked').each(function () {
                $(this).show();
                var row = $(this).closest('tr');
                row.find('.row-spinner').toggleClass('d-none');
            });
            // re-enable all action buttons
            $('#' + actionBtnId).prop('disabled', false);
        },
        error: function (result) {
            // hide spinners
            $('.tr-checkbox:checked').each(function () {
                $(this).show();
                var row = $(this).closest('tr');
                row.find('.row-spinner').toggleClass('d-none');
            });
            // re-enable all action buttons
            $('#' + actionBtnId).prop('disabled', false);
        }
    });
}

$('#btn-delete').click(function () {
    performAction('delete', 'btn-delete');
});

$('#btn-start').click(function () {
    performAction('start', 'btn-start');
});

$('#btn-stop').click(function () {
    performAction('stop', 'btn-stop');
});

$('#btn-kill').click(function () {
    performAction('kill', 'btn-kill');
});

$('#btn-restart').click(function () {
    performAction('restart', 'btn-restart');
});

$('#btn-pause').click(function () {
    performAction('pause', 'btn-pause');
});

$('#btn-resume').click(function () {
    performAction('resume', 'btn-resume');
});