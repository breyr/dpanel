// toggle buttons based on checkboxes for rows
$(document).on('change', '.tr-checkbox', function () {
    var checkedCount = $('.tr-checkbox:checked').length;
    console.log(checkedCount);
    // Then, enable the correct buttons based on the status
    if (checkedCount > 0) {
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').removeClass('disabled');
    } else {
        // If no checkboxes are checked, disable all buttons
        $('#btn-stop, #btn-kill, #btn-restart, #btn-pause, #btn-delete, #btn-resume, #btn-start').addClass('disabled');
    }
});