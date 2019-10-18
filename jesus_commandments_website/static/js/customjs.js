$(document).ready(function(){
  
  if($.cookie('jc_bible_trans_settings')){
    $('#changeLanguageModal').modal('show');
    $.removeCookie('jc_bible_trans_settings');
  }
  
  
  // ----- Detailed commandments page: Smooth scrolling BEGIN ------ \\  
    // Add smooth scrolling to all links
    $("a").on('click', function(event) {

      // Make sure this.hash has a value before overriding default behavior
      if (this.hash !== "") {
        // Prevent default anchor click behavior
        event.preventDefault();

        // Store hash
        var hash = this.hash;

        // Using jQuery's animate() method to add smooth page scroll
        // The optional number (800) specifies the number of milliseconds it takes to scroll to the specified area
        $('html, body').animate({
          scrollTop: $(hash).offset().top
        }, 800, function(){

          // Add hash (#) to URL when done scrolling (default click behavior)
          window.location.hash = hash;
        });
      } // End if
    });
    // ----- Detailed commandments page: Smooth scrolling END ------ \\ 






    // ----- Study Listing arrows in table BEGIN ------ \\ 
    $('#dtBasicExample').DataTable();
      $('.dataTables_length').addClass('bs-select');
    // ----- Study Listing arrows in table END ------ \\ 







    // ----- Showing and hiding tooltip with different speed BEGIN ------ \\ 
    $(".select").tooltip({
        delay: {show: 0, hide: 1000}
    });
    // ----- Showing and hiding tooltip with different speed END ------ \\ 



    $(document).on('change', '.drpSelectLanguage', function(event){
      event.preventDefault();
      $.cookie('jc_bible_trans_settings', true);
      debugger;
      this.form.submit();
    });
    $(document).on('change', '.drpBibleTranslation', function(event){
      event.preventDefault();
      $.cookie('jc_bible_trans_settings', true);
      this.form.submit();
    });

    $(document).on('click', '.btnSaveLanguages', function(event){
      event.preventDefault();
      //$.cookie('jc_bible_trans_settings', true);
      this.form.submit();
    });
  });