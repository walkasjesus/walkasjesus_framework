$(document).ready(function(){

  // Normalize YouTube iframe permissions to avoid browser policy warnings.
  $('iframe[src*="youtube.com/embed/"], iframe[src*="youtube-nocookie.com/embed/"]').each(function() {
    var $iframe = $(this);
    $iframe.attr('allow', 'accelerometer; autoplay; clipboard-write; encrypted-media; gyroscope; picture-in-picture; web-share');
    $iframe.attr('allowfullscreen', 'allowfullscreen');
    if (!$iframe.attr('referrerpolicy')) {
      $iframe.attr('referrerpolicy', 'strict-origin-when-cross-origin');
    }
  });

  var verseCache = {};
  var verseSourceCache = {};
  var verseFetchInFlight = {};
  var scripturaChapterCache = {};
  var sefariaRelatedCache = {};
  var sefariaTextCache = {};
  var translationCache = {};

  function verseSpinnerHtml(source) {
    var spinnerClass = source === 'api' ? 'verse-loading-spinner verse-loading-spinner-api' : 'verse-loading-spinner verse-loading-spinner-cache';
    return '<i class="fa fa-spinner fa-spin ' + spinnerClass + '"></i>';
  }

  function commentarySpinnerHtml(source, label) {
    var spinnerClass = source === 'api' ? 'commentary-loading-spinner commentary-loading-spinner-api' : 'commentary-loading-spinner commentary-loading-spinner-cache';
    var text = label ? (' ' + label) : '';
    return '<i class="fa fa-spinner fa-spin ' + spinnerClass + '"></i>' + text;
  }

  function collectRefIds(selector) {
    var ids = [];
    $(selector).each(function() {
      var pk = String($(this).attr('data-verse-ref') || '').trim();
      if (pk) {
        ids.push(pk);
      }
    });
    return Array.from(new Set(ids));
  }

  function fetchVerses(versesUrl, refIds, onDone) {
    if (!versesUrl || !refIds || refIds.length === 0) {
      if (onDone) onDone({});
      return;
    }

    $.ajax({
      type: 'POST',
      url: versesUrl,
      timeout: 20000,
      data: {
        csrfmiddlewaretoken: getCsrfToken(),
        verse_refs: refIds
      },
      success: function(data) {
        var verses = (data && data.verses) ? data.verses : {};
        var verseSources = (data && data.verse_sources) ? data.verse_sources : {};
        $.each(verses, function(pk, text) {
          verseCache[String(pk)] = text;
        });
        $.each(verseSources, function(pk, source) {
          verseSourceCache[String(pk)] = String(source || '');
        });
        if (onDone) onDone(verses, verseSources);
      },
      error: function(xhr) {
        console.error('Failed to load bible verses:', xhr.status, xhr.responseText);
        if (onDone) onDone({});
      }
    });
  }

  function revealManualVerse($link, pk) {
    var text = verseCache[pk];
    if (typeof text === 'undefined') {
      return false;
    }

    renderVerseText($('.bible-verse-text[data-verse-ref="' + pk + '"][data-verse-manual="1"]'), text);
    // Hide the line breaks around the now-hidden "Click to retrieve" button.
    $link.prev('br').hide();
    $link.nextAll('br').first().hide();
    $link.hide();
    return true;
  }

  function renderVerseText($elements, text) {
    $elements.each(function() {
      var $element = $(this);
      $element.empty().text(text);
    });
  }

  function getCsrfToken() {
    // Try cookie first (works on HTTPS), fall back to DOM (works on HTTP dev)
    var match = document.cookie.match(/csrftoken=([^;]+)/);
    if (match) return match[1];
    var input = document.querySelector('[name=csrfmiddlewaretoken]');
    return input ? input.value : '';
  }

  function getVersesUrl() {
    var container = document.querySelector('[data-verses-url]');
    return container ? container.getAttribute('data-verses-url') : '';
  }

  function resolveVersesUrl($el) {
    var ownUrl = String($el.attr('data-verses-url') || '').trim();
    if (ownUrl) {
      return ownUrl;
    }

    var nearestUrl = String($el.closest('[data-verses-url]').attr('data-verses-url') || '').trim();
    if (nearestUrl) {
      return nearestUrl;
    }

    return String(getVersesUrl() || '').trim();
  }

  function ensureManualVerseTarget($link, pk) {
    var $target = $('.bible-verse-text[data-verse-ref="' + pk + '"][data-verse-manual="1"]').first();
    if (!$target.length) {
      return $target;
    }

    if (!$target.data('jcVersePrepared')) {
      $target.css({ display: 'block' });
      $target.insertBefore($link);
      $target.data('jcVersePrepared', true);
    }

    return $target;
  }

  function getCommentaryLanguage() {
    if ($.cookie) {
      var cookieLanguage = String($.cookie('django_language') || '').trim().toLowerCase();
      if (cookieLanguage) {
        return cookieLanguage.slice(0, 2);
      }
    }
    var container = document.querySelector('[data-commentary-language]');
    return container ? String(container.getAttribute('data-commentary-language') || 'en').trim().toLowerCase() : 'en';
  }

  function getCommentaryTranslateUrl() {
    var container = document.querySelector('[data-commentary-translate-url]');
    return container ? container.getAttribute('data-commentary-translate-url') : '';
  }

  function getCommentaryScripturaUrl() {
    var container = document.querySelector('[data-commentary-scriptura-url]');
    return container ? container.getAttribute('data-commentary-scriptura-url') : '';
  }

  function uiMessage(key, variables) {
    var lang = getCommentaryLanguage() === 'nl' ? 'nl' : 'en';
    var messages = {
      loading_commentary: {
        en: 'Loading commentary...',
        nl: 'Commentaar laden...'
      },
      no_commentary_scriptura_chapter: {
        en: 'No commentary found for this chapter on BijbelAPI.',
        nl: 'Geen commentaar gevonden voor dit hoofdstuk op BijbelAPI.'
      },
      no_exact_scriptura_verse: {
        en: 'No exact commentary was found for verse {verse}. Choose an available entry from this chapter.',
        nl: 'Geen exacte toelichting gevonden voor vers {verse}. Kies een beschikbare toelichting uit dit hoofdstuk.'
      },
      select_available_commentary: {
        en: 'Select an available commentary:',
        nl: 'Kies een beschikbare toelichting:'
      },
      could_not_load_scriptura: {
        en: 'Could not load commentary from BijbelAPI.',
        nl: 'Kon commentaar van BijbelAPI niet laden.'
      },
      select_commentator: {
        en: 'Select a commentator:',
        nl: 'Kies een commentator:'
      },
      could_not_reach_sefaria: {
        en: 'Could not reach Sefaria API. Please check your connection.',
        nl: 'Kan Sefaria API niet bereiken. Controleer je verbinding.'
      },
      no_jewish_commentary_for_reference: {
        en: 'No Jewish commentary found for this reference on Sefaria.',
        nl: 'Geen Joodse toelichting gevonden voor deze verwijzing op Sefaria.'
      },
      jewish_commentary_by_sefaria: {
        en: 'Jewish commentary provided by',
        nl: 'Joodse toelichting aangeboden door'
      },
      loading_commentator: {
        en: 'Loading {name}...',
        nl: '{name} laden...'
      },
      machine_translated_from_en: {
        en: 'Machine translated from English.',
        nl: 'Automatisch vertaald vanuit het Engels.'
      },
      view_on_sefaria: {
        en: 'View on Sefaria',
        nl: 'Bekijk op Sefaria'
      },
      no_english_text_available: {
        en: 'No English text available for {name} on this passage.',
        nl: 'Geen Engelse tekst beschikbaar voor {name} bij deze passage.'
      },
      complex_structure_on_sefaria: {
        en: '{name} has a complex structure on Sefaria.',
        nl: '{name} heeft een complexe structuur op Sefaria.'
      },
      could_not_load_commentary_text: {
        en: 'Could not load commentary text for {name}.',
        nl: 'Kon commentaartekst voor {name} niet laden.'
      },
      could_not_load_verse_text: {
        en: 'Could not load verse text.',
        nl: 'Kon bijbeltekst niet laden.'
      }
    };

    var template = (messages[key] && messages[key][lang]) || (messages[key] && messages[key].en) || key;
    if (!variables) {
      return template;
    }

    return template.replace(/\{(\w+)\}/g, function(_, variableKey) {
      return typeof variables[variableKey] === 'undefined' ? '' : String(variables[variableKey]);
    });
  }

  function getCommentaryCacheTimeoutSeconds() {
    var container = document.querySelector('[data-commentary-cache-timeout]');
    var rawValue = container ? container.getAttribute('data-commentary-cache-timeout') : '';
    var parsed = parseInt(rawValue, 10);
    if (!isNaN(parsed) && parsed > 0) {
      return parsed;
    }
    return 60 * 60 * 24 * 30 * 6;
  }

  function commentaryStorageKey(bucket, key) {
    return 'jc_commentary_cache:v1:' + bucket + ':' + key;
  }

  function getCommentaryCachedValue(cacheStore, bucket, key) {
    if (typeof cacheStore[key] !== 'undefined') {
      return cacheStore[key];
    }

    try {
      var raw = localStorage.getItem(commentaryStorageKey(bucket, key));
      if (!raw) {
        return undefined;
      }

      var parsed = JSON.parse(raw);
      if (!parsed || typeof parsed.expires_at !== 'number') {
        localStorage.removeItem(commentaryStorageKey(bucket, key));
        return undefined;
      }

      if (Date.now() > parsed.expires_at) {
        localStorage.removeItem(commentaryStorageKey(bucket, key));
        return undefined;
      }

      cacheStore[key] = parsed.value;
      return parsed.value;
    } catch (error) {
      return undefined;
    }
  }

  function setCommentaryCachedValue(cacheStore, bucket, key, value) {
    cacheStore[key] = value;
    try {
      localStorage.setItem(
        commentaryStorageKey(bucket, key),
        JSON.stringify({
          value: value,
          expires_at: Date.now() + (getCommentaryCacheTimeoutSeconds() * 1000)
        })
      );
    } catch (error) {
      // Ignore storage failures (private mode/quota exceeded)
    }
  }

  function translateCommentaryText(text, onDone) {
    var targetLanguage = getCommentaryLanguage();
    var translateUrl = getCommentaryTranslateUrl();
    var cacheKey = targetLanguage + '|' + String(text || '');
    var translationCached = getCommentaryCachedValue(translationCache, 'translation', cacheKey);

    if (translationCached) {
      if (onDone) onDone(translationCached.translated_text, translationCached.machine_translated);
      return;
    }

    if (!text || !translateUrl || !targetLanguage || targetLanguage === 'en') {
      if (onDone) onDone(text, false);
      return;
    }

    $.ajax({
      type: 'POST',
      url: translateUrl,
      data: {
        csrfmiddlewaretoken: getCsrfToken(),
        text: text,
        target_language: targetLanguage
      },
      success: function(data) {
        if (data && data.translated_text) {
          setCommentaryCachedValue(translationCache, 'translation', cacheKey, {
            translated_text: data.translated_text,
            machine_translated: !!data.machine_translated
          });
          if (onDone) onDone(data.translated_text, !!data.machine_translated);
          return;
        }
        if (onDone) onDone(text, false);
      },
      error: function(xhr) {
        console.error('Failed to translate commentary text:', xhr.status, xhr.responseText);
        if (onDone) onDone(text, false);
      }
    });
  }

  function sanitizeSefariaHtml(html) {
    if (!html) {
      return '';
    }

    var template = document.createElement('template');
    template.innerHTML = html;
    var allowedTags = {
      A: true,
      B: true,
      BR: true,
      EM: true,
      I: true,
      SMALL: true,
      SPAN: true,
      STRONG: true,
      SUB: true,
      SUP: true,
      U: true
    };

    function cleanNode(node) {
      var children = Array.prototype.slice.call(node.childNodes || []);
      children.forEach(function(child) {
        if (child.nodeType === Node.TEXT_NODE) {
          return;
        }

        if (child.nodeType !== Node.ELEMENT_NODE) {
          node.removeChild(child);
          return;
        }

        var tagName = child.tagName.toUpperCase();
        if (!allowedTags[tagName]) {
          while (child.firstChild) {
            node.insertBefore(child.firstChild, child);
          }
          node.removeChild(child);
          return;
        }

        Array.prototype.slice.call(child.attributes).forEach(function(attribute) {
          var name = attribute.name.toLowerCase();
          if (tagName === 'A' && (name === 'href' || name === 'target' || name === 'rel')) {
            return;
          }
          if (tagName === 'SPAN' && name === 'class' && attribute.value === 'font1') {
            return;
          }
          child.removeAttribute(attribute.name);
        });

        if (tagName === 'A') {
          var href = child.getAttribute('href') || '';
          if (!/^https?:\/\//i.test(href)) {
            child.removeAttribute('href');
          } else {
            child.setAttribute('target', '_blank');
            child.setAttribute('rel', 'noopener noreferrer');
          }
        }

        cleanNode(child);
      });
    }

    cleanNode(template.content);
    return template.innerHTML;
  }

  // Auto-load bible verse texts on detail pages
  var versesUrl = getVersesUrl();
  if (versesUrl) {
    var autoRefIds = collectRefIds('.bible-verse-text[data-verse-ref]:not([data-verse-manual="1"])');
    if (autoRefIds.length > 0) {
      // Show API spinner style while the first fetch for this page is pending.
      $('.bible-verse-text[data-verse-ref]:not([data-verse-manual="1"])').html(verseSpinnerHtml('api'));
      console.debug('Loading bible verses from:', versesUrl, 'refs:', autoRefIds.length);
      fetchVerses(versesUrl, autoRefIds, function(verses) {
        $.each(verses, function(pk, text) {
          renderVerseText($('.bible-verse-text[data-verse-ref="' + pk + '"]:not([data-verse-manual="1"])'), text);
        });
      });
    }
  }

  $(document).on('click', '.bible-verse-load-link', function(event) {
    event.preventDefault();
    var $link = $(this);
    var pk = String($link.attr('data-verse-ref') || '').trim();
    var requestVersesUrl = resolveVersesUrl($link);
    var $manualTarget = ensureManualVerseTarget($link, pk);

    if (!pk) {
      return;
    }

    if (!revealManualVerse($link, pk)) {
      if (verseFetchInFlight[pk]) {
        return;
      }

      verseFetchInFlight[pk] = true;
      if ($manualTarget.length) {
        var spinnerSource = verseSourceCache[pk] || (typeof verseCache[pk] === 'undefined' ? 'api' : 'cache');
        $manualTarget.html(verseSpinnerHtml(spinnerSource));
      }
      fetchVerses(requestVersesUrl, [pk], function() {
        if (!revealManualVerse($link, pk)) {
          if ($manualTarget.length) {
            $manualTarget.text(uiMessage('could_not_load_verse_text'));
          }
        }
        verseFetchInFlight[pk] = false;
      });
    }
  });

  if($.cookie('jc_bible_trans_settings')){
    $('#changeLanguageModal').modal('show');
    $.removeCookie('jc_bible_trans_settings');
  }  

  function refreshAudienceBoundSections() {
    $('.our-services-wrapper').each(function() {
      var $wrapper = $(this);
      var $section = $wrapper.closest('.col-xl-12, .col-lg-12, .col-md-12, .col-sm-12');
      if (!$section.length) {
        return;
      }

      var $audienceNodes = $section.filter('[targetaudience]').add($section.find('[targetaudience]'));
      if (!$audienceNodes.length) {
        return;
      }

      // Reset section visibility first so visibility checks only depend on audience-node display.
      $section.show();
      var hasVisibleAudienceNode = $audienceNodes.filter(function() {
        return $(this).css('display') !== 'none';
      }).length > 0;

      if (!hasVisibleAudienceNode) {
        $section.hide();
      }
    });
  }

  function applyKidsModeState(isKidsMode, animated) {
    var showFn = animated ? 'slideDown' : 'show';
    var hideFn = animated ? 'slideUp' : 'hide';

    if (isKidsMode) {
      $('[targetaudience="kids"]')[showFn]();
      $('[targetaudience="adults"]')[hideFn]();
      $('.kids-mode-hide')[hideFn]();
      $('.chk-kids-mode').prop('checked', true);
      refreshAudienceBoundSections();
      return;
    }

    $('[targetaudience="kids"]')[hideFn]();
    $('[targetaudience="adults"]')[showFn]();
    $('.kids-mode-hide')[showFn]();
    $('.chk-kids-mode').prop('checked', false);
    refreshAudienceBoundSections();
  }

  if($.cookie('jc_kids_mode')){
    applyKidsModeState(true, false);
  }
  else {
    applyKidsModeState(false, false);
  }

  $(document).on('change', '.chk-kids-mode', function(event){
    // var checked = document.getElementById('chk-kids-mode-1').checked;
    var checked = $(this).prop('checked');
    if (checked){
      $.cookie('jc_kids_mode', true, { expires: 365 });
      applyKidsModeState(true, true);
    }
    else {
      $.removeCookie('jc_kids_mode');
      applyKidsModeState(false, true);
    }

    // Load server-filtered content for the selected audience mode.
    window.location.reload();
  });

  const introVid = $("#WaJ-intro-video");
  if(introVid.length){
    const lang = $.cookie('django_language');
    if(lang === 'nl'){
      introVid.attr('src', 'https://www.youtube.com/embed/eTc08O8qEm0');
    } else {
      introVid.attr('src', '');
    }
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
    // $(".select").tooltip({
    //     delay: {show: 0, hide: 0}
    // });

    $(function () {
      $('[data-toggle="kids-tooltip"]').tooltip({ trigger: "hover" })
    })
    // ----- Showing and hiding tooltip with different speed END ------ \\ 

    $(document).on('change', '.drpSelectLanguage', function(event){
      event.preventDefault();
      $(this).trigger('jc:site-language-changed', [$(this).val()]);
    });
    $(document).on('change', '.drpBibleTranslation', function(event){
      event.preventDefault();
      $(this).trigger('jc:bible-translation-changed', [$(this).val()]);
    });

    $(document).on('click', '.btnSaveLanguages', function(event){
      event.preventDefault();
      $(this).trigger('jc:save-language-bible-settings');
    });

    // ----- Sefaria Jewish Commentary BEGIN ------ \\

    function sefariaExtractText(textData) {
      if (typeof textData === 'string') return textData;
      if (Array.isArray(textData)) {
        return textData.map(function(t) { return sefariaExtractText(t); }).filter(Boolean).join('<br>');
      }
      return '';
    }

    function getScripturaCommentators() {
      var isDutch = getCommentaryLanguage() === 'nl';
      return [
        {
          id: 'david-stern',
          label: 'David Stern',
          apiSources: ['david-stern', 'david_stern', 'jnt-stern', 'jnt_stern'],
          autoTranslate: true
        },
        {
          id: 'matthew-henry',
          label: isDutch ? 'Matthew Henry (NL)' : 'Matthew Henry',
          apiSources: isDutch
            ? ['matthew_henry_nl', 'matthew-henry-nl', 'matthew_henry', 'matthew-henry']
            : ['matthew_henry', 'matthew-henry'],
          autoTranslate: !isDutch
        }
      ];
    }

    function getScripturaCommentatorById(commentatorId) {
      var commentators = getScripturaCommentators();
      for (var i = 0; i < commentators.length; i += 1) {
        if (commentators[i].id === commentatorId) {
          return commentators[i];
        }
      }
      return commentators[0];
    }

    function isNewTestamentBook(book) {
      var normalized = String(book || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      var ntBooks = {
        matthew: true,
        mark: true,
        luke: true,
        john: true,
        acts: true,
        romans: true,
        '1corinthians': true,
        '2corinthians': true,
        galatians: true,
        ephesians: true,
        philippians: true,
        colossians: true,
        '1thessalonians': true,
        '2thessalonians': true,
        '1timothy': true,
        '2timothy': true,
        titus: true,
        philemon: true,
        hebrews: true,
        james: true,
        '1peter': true,
        '2peter': true,
        '1john': true,
        '2john': true,
        '3john': true,
        jude: true,
        revelation: true
      };
      return !!ntBooks[normalized];
    }

    function getDefaultScripturaCommentatorId(book) {
      return isNewTestamentBook(book) ? 'david-stern' : 'matthew-henry';
    }

    function getScripturaEndpoints() {
      var proxyUrl = String(getCommentaryScripturaUrl() || '').trim();
      if (proxyUrl) {
        return [proxyUrl];
      }
      return ['https://www.bijbelapi.com/api/commentary', 'https://bijbelapi.com/api/commentary'];
    }

    function escapeScripturaParam(value) {
      return encodeURIComponent(String(value || '').trim());
    }

    function scripturaCommentaryUrl(endpoint, source, book, chapter, verse) {
      var separator = endpoint.indexOf('?') === -1 ? '?' : '&';
      var url = endpoint + separator + 'source=' + escapeScripturaParam(source) + '&book=' + escapeScripturaParam(book) + '&chapter=' + escapeScripturaParam(chapter);
      if (typeof verse !== 'undefined' && verse !== null && String(verse) !== '') {
        url += '&verse=' + escapeScripturaParam(verse);
      }
      return url;
    }

    function fetchScripturaCommentary(book, chapter, commentator, onSuccess, onError) {
      var endpoints = getScripturaEndpoints();
      var sources = (commentator && commentator.apiSources) ? commentator.apiSources : [];
      var candidates = [];

      endpoints.forEach(function(endpoint) {
        sources.forEach(function(source) {
          candidates.push({
            endpoint: endpoint,
            source: source,
            url: scripturaCommentaryUrl(endpoint, source, book, chapter)
          });
        });
      });

      function tryCandidate(index) {
        if (index >= candidates.length) {
          if (onError) onError();
          return;
        }

        var candidate = candidates[index];
        $.ajax({
          url: candidate.url,
          type: 'GET',
          success: function(data) {
            if (data && typeof data === 'object' && Object.keys(data).length > 0) {
              if (onSuccess) onSuccess(data, candidate.source, candidate.endpoint);
              return;
            }
            tryCandidate(index + 1);
          },
          error: function() {
            tryCandidate(index + 1);
          }
        });
      }

      tryCandidate(0);
    }

    function scripturaEntryLabel(entryKey) {
      if (String(entryKey) === '0') {
        return getCommentaryLanguage() === 'nl' ? 'Inleiding' : 'Intro';
      }
      return getCommentaryLanguage() === 'nl' ? ('Vers ' + entryKey) : ('Verse ' + entryKey);
    }

    function buildScripturaSourceButtons(activeCommentatorId) {
      var html = '<div class="scriptura-commentary-sources">' +
        '<p class="sefaria-select-label">' + uiMessage('select_commentator') + '</p>';

      getScripturaCommentators().forEach(function(commentator) {
        var activeClass = commentator.id === activeCommentatorId ? ' active' : '';
        html += '<button class="btn btn-sm sefaria-commentator-btn scriptura-commentary-source-btn mr-1 mb-1' + activeClass + '" data-scriptura-commentator="' + $('<span>').text(commentator.id).html() + '">' +
          $('<span>').text(commentator.label).html() +
          '</button>';
      });

      html += '</div>';
      return html;
    }

    function renderScripturaEntry($panel, entryKey, commentaryText, source, book, chapter, endpoint, commentator) {
      var titleLabel = scripturaEntryLabel(entryKey);
      var sourceLabel = (commentator && commentator.label) ? commentator.label : 'Commentary';
      var scripturaUrl = scripturaCommentaryUrl(endpoint || getScripturaEndpoints()[0], source, book, chapter, entryKey);
      var shouldTranslate = !!(commentator && commentator.autoTranslate);
      var renderToken = String(Date.now()) + ':' + String(Math.random());

      $panel.data('scripturaRenderToken', renderToken);
      $panel.find('.scriptura-commentary-entry-btn').removeClass('active');
      $panel.find('.scriptura-commentary-entry-btn[data-entry-key="' + entryKey + '"]').addClass('active');
      $panel.find('.scriptura-commentary-text').html(commentarySpinnerHtml('api', uiMessage('loading_commentary')));

      function renderCommentaryBody(rawText, isMachineTranslated) {
        if ($panel.data('scripturaRenderToken') !== renderToken) {
          return;
        }

        var safeHtml = sanitizeSefariaHtml(String(rawText || '').replace(/\n/g, '<br>'));
        var displayHtml = safeHtml || $('<span>').text(rawText || '').html().replace(/\n/g, '<br>');
        var translationNote = '';
        if (isMachineTranslated) {
          translationNote = '<p class="sefaria-attribution"><em>' + uiMessage('machine_translated_from_en') + '</em></p>';
        }

        $panel.find('.scriptura-commentary-text').html(
          '<div class="sefaria-commentary-content">' +
          '<strong>' + $('<span>').text(sourceLabel).html() + ' · ' + $('<span>').text(titleLabel).html() + '</strong>' +
          translationNote +
          '<div class="sefaria-commentary-body mt-1">' + displayHtml + '</div>' +
          '<p class="sefaria-attribution">Commentary provided by <a href="https://www.bijbelapi.com/" target="_blank" rel="noopener noreferrer">BijbelAPI</a> · <a href="' + scripturaUrl + '" target="_blank" rel="noopener noreferrer">Open API response</a></p>' +
          '</div>'
        );
      }

      if (!shouldTranslate) {
        renderCommentaryBody(commentaryText || '', false);
        return;
      }

      translateCommentaryText(String(commentaryText || ''), function(translatedText, isMachineTranslated) {
        renderCommentaryBody(translatedText, isMachineTranslated);
      });
    }

    function renderScripturaSourceContent($panel, entries, verse, commentator, source, book, chapter, endpoint) {
      var entryKeys = Object.keys(entries || {}).filter(function(key) {
        return key.indexOf('__') !== 0 && entries[key];
      }).sort(function(a, b) {
        return Number(a) - Number(b);
      });

      if (entryKeys.length === 0) {
        $panel.find('.scriptura-commentary-source-content').html(
          '<p class="sefaria-no-result"><em>' + uiMessage('no_commentary_scriptura_chapter') + '</em></p>'
        );
        return;
      }

      var html = '';
      if (!entries[String(verse)]) {
        html += '<p class="sefaria-no-result scriptura-commentary-hint"><em>' +
          uiMessage('no_exact_scriptura_verse', { verse: $('<span>').text(String(verse)).html() }) +
          '</em></p>';
      }

      html += '<div class="scriptura-commentators"><p class="sefaria-select-label">' + uiMessage('select_available_commentary') + '</p>';
      entryKeys.forEach(function(entryKey) {
        html += '<button class="btn btn-sm sefaria-commentator-btn scriptura-commentary-entry-btn mr-1 mb-1" data-entry-key="' + $('<span>').text(entryKey).html() + '">' + $('<span>').text(scripturaEntryLabel(entryKey)).html() + '</button>';
      });
      html += '</div><div class="scriptura-commentary-text"></div>';

      $panel.find('.scriptura-commentary-source-content').html(html);
      $panel.data('scripturaEntries', entries);
      $panel.data('scripturaSource', source);
      $panel.data('scripturaEndpoint', endpoint);
      $panel.data('scripturaBook', book);
      $panel.data('scripturaChapter', chapter);
      $panel.data('scripturaCommentatorId', commentator.id);

      var preferredKey = entries[String(verse)] ? String(verse) : (entryKeys.indexOf('0') !== -1 ? '0' : entryKeys[0]);
      renderScripturaEntry($panel, preferredKey, entries[preferredKey], source, book, chapter, endpoint, commentator);
    }

    function loadScripturaCommentaryForCommentator($panel, commentatorId, preferredVerse) {
      var book = $panel.data('scripturaBook');
      var chapter = $panel.data('scripturaChapter');
      var verse = typeof preferredVerse === 'undefined' ? $panel.data('scripturaVerse') : preferredVerse;
      var commentator = getScripturaCommentatorById(commentatorId);
      var chapterCacheKey = [commentator.id, String(book || ''), String(chapter || '')].join('|');
      var cachedEntries = getCommentaryCachedValue(scripturaChapterCache, 'scriptura_chapter', chapterCacheKey);

      $panel.find('.scriptura-commentary-source-btn').removeClass('active');
      $panel.find('.scriptura-commentary-source-btn[data-scriptura-commentator="' + commentator.id + '"]').addClass('active');

      if (cachedEntries) {
        renderScripturaSourceContent(
          $panel,
          cachedEntries,
          verse,
          commentator,
          cachedEntries.__source || commentator.apiSources[0],
          book,
          chapter,
          cachedEntries.__endpoint || getScripturaEndpoints()[0]
        );
        return;
      }

      $panel.find('.scriptura-commentary-source-content').html(commentarySpinnerHtml('api', uiMessage('loading_commentary')));

      fetchScripturaCommentary(book, chapter, commentator, function(data, resolvedSource, resolvedHost) {
        var entries = data || {};
        entries.__source = resolvedSource;
        entries.__endpoint = resolvedHost;
        setCommentaryCachedValue(scripturaChapterCache, 'scriptura_chapter', chapterCacheKey, entries);
        renderScripturaSourceContent($panel, entries, verse, commentator, resolvedSource, book, chapter, resolvedHost);
      }, function() {
        console.log('[BijbelAPI] Commentary request failed for all configured hosts/sources');
        $panel.find('.scriptura-commentary-source-content').html('<p class="sefaria-no-result"><em>' + uiMessage('could_not_load_scriptura') + '</em></p>');
      });
    }

    $(document).on('click', '.scriptura-commentary-btn', function() {
      var $btn = $(this);
      var book = $btn.data('scriptura-book');
      var chapter = $btn.data('scriptura-chapter');
      var verse = $btn.data('scriptura-verse');
      var $panel = $btn.nextAll('.scriptura-commentary-panel').first();
      var preferredCommentatorId = getDefaultScripturaCommentatorId(book);

      if ($panel.is(':visible')) {
        $panel.slideUp(200);
        return;
      }

      $panel.html(buildScripturaSourceButtons(preferredCommentatorId) + '<div class="scriptura-commentary-source-content">' + commentarySpinnerHtml('api', uiMessage('loading_commentary')) + '</div>').slideDown(200);
      $panel.data('scripturaBook', book);
      $panel.data('scripturaChapter', chapter);
      $panel.data('scripturaVerse', verse);

      loadScripturaCommentaryForCommentator($panel, preferredCommentatorId, verse);
    });

    $(document).on('click', '.scriptura-commentary-source-btn', function() {
      var $btn = $(this);
      var commentatorId = String($btn.data('scriptura-commentator') || '');
      var $panel = $btn.closest('.scriptura-commentary-panel');
      if (!commentatorId || !$panel.length) {
        return;
      }
      loadScripturaCommentaryForCommentator($panel, commentatorId);
    });

    $(document).on('click', '.scriptura-commentary-entry-btn', function() {
      var $btn = $(this);
      var $panel = $btn.closest('.scriptura-commentary-panel');
      var entries = $panel.data('scripturaEntries') || {};
      var source = $panel.data('scripturaSource');
      var scripturaEndpoint = $panel.data('scripturaEndpoint') || getScripturaEndpoints()[0];
      var book = $panel.data('scripturaBook');
      var chapter = $panel.data('scripturaChapter');
      var commentatorId = $panel.data('scripturaCommentatorId');
      var commentator = getScripturaCommentatorById(commentatorId);
      var entryKey = String($btn.data('entry-key'));
      var commentaryText = entries[entryKey] || '';

      if (!commentaryText) {
        return;
      }

      renderScripturaEntry($panel, entryKey, commentaryText, source, book, chapter, scripturaEndpoint, commentator);
    });

    $(document).on('click', '.sefaria-commentary-btn', function() {
      var $btn = $(this);
      var ref = $btn.data('sefaria-ref');
      if (!ref) {
        return;
      }
      var $panel = $btn.next('.sefaria-commentary-panel');
      var cachedRelatedHtml = getCommentaryCachedValue(sefariaRelatedCache, 'sefaria_related', ref);

      if ($panel.is(':visible')) {
        $panel.slideUp(200);
        return;
      }

      if (cachedRelatedHtml) {
        $panel.html(commentarySpinnerHtml('cache', uiMessage('loading_commentary'))).slideDown(200);
        $panel.html(cachedRelatedHtml).slideDown(200);
        return;
      }

      $panel.html(commentarySpinnerHtml('api', uiMessage('loading_commentary'))).slideDown(200);

      var apiUrl = 'https://www.sefaria.org/api/related/' + encodeURIComponent(ref);
      console.log('[Sefaria] Fetching related for ref:', ref);
      console.log('[Sefaria] URL:', apiUrl);

      $.ajax({
        url: apiUrl,
        type: 'GET',
        success: function(data) {
          console.log('[Sefaria] Related API response:', data);
          var links = (data && data.links) ? data.links : [];
          var commentators = {};
          $.each(links, function(i, link) {
            if (link.type === 'commentary' && link.collectiveTitle && link.collectiveTitle.en) {
              var name = link.collectiveTitle.en;
              if (!commentators[name]) {
                commentators[name] = { hasEn: !!link.sourceHasEn };
              } else if (link.sourceHasEn) {
                commentators[name].hasEn = true;
              }
            }
          });

          var names = Object.keys(commentators);
          console.log('[Sefaria] Commentary links found:', links.filter(function(l){ return l.type === 'commentary'; }).length, 'of', links.length, 'total links');
          console.log('[Sefaria] Unique commentators:', names);
          
          // Filter to only commentators with English text
          var englishNames = names.filter(function(name) { return commentators[name].hasEn; });
          console.log('[Sefaria] English commentaries:', englishNames);
          
          if (englishNames.length === 0) {
            $panel.html('<p class="sefaria-no-result"><em>' + uiMessage('no_jewish_commentary_for_reference') + '</em></p>');
            return;
          }

          var html = '<div class="sefaria-commentators"><p class="sefaria-select-label">' + uiMessage('select_commentator') + '</p>';
          $.each(englishNames, function(i, name) {
            var safeName = $('<span>').text(name).html();
            var safeRef = $('<span>').text(ref).html();
            html += '<button class="btn btn-sm sefaria-commentator-btn mr-1 mb-1" data-commentator="' + safeName + '" data-ref="' + safeRef + '">' + safeName + '</button>';
          });
          html += '</div><div class="sefaria-commentary-text"></div><p class="sefaria-attribution" style="font-size:10px; margin-top:10px; color:#999;">' + uiMessage('jewish_commentary_by_sefaria') + ' <a href="https://www.sefaria.org/" target="_blank" rel="noopener noreferrer" style="color:#5c4a1e;">Sefaria</a></p>';
          setCommentaryCachedValue(sefariaRelatedCache, 'sefaria_related', ref, html);
          $panel.html(html);
        },
        error: function() {
          $panel.html('<p class="sefaria-no-result"><em>' + uiMessage('could_not_reach_sefaria') + '</em></p>');
        }
      });
    });

    $(document).on('click', '.sefaria-commentary-panel .sefaria-commentator-btn', function() {
      var $btn = $(this);
      var commentator = $btn.data('commentator');
      var ref = $btn.data('ref');

      if (!commentator || !ref) {
        return;
      }

      var $panel = $btn.closest('.sefaria-commentary-panel');
      var $textDiv = $panel.find('.sefaria-commentary-text');
      var fullRef = commentator + ' on ' + ref;
      var cachedCommentary = getCommentaryCachedValue(sefariaTextCache, 'sefaria_text', fullRef);

      $panel.find('.sefaria-commentator-btn').removeClass('active');
      $btn.addClass('active');
      $textDiv.html(commentarySpinnerHtml(cachedCommentary ? 'cache' : 'api', uiMessage('loading_commentator', { name: $('<span>').text(commentator).html() })));

      var escapedName = $('<span>').text(commentator).html();

      function renderCommentaryText(bodyText, sefariaUrl, isMachineTranslated) {
        var sanitizedHtml = sanitizeSefariaHtml(bodyText || '');
        var displayText = sanitizedHtml || $('<span>').text(bodyText || '').html().replace(/\n/g, '<br>');
        var translationNote = '';
        if (isMachineTranslated) {
          translationNote = '<p class="sefaria-attribution"><em>' + uiMessage('machine_translated_from_en') + '</em></p>';
        }

        $textDiv.html(
          '<div class="sefaria-commentary-content">' +
          '<strong>' + escapedName + '</strong>' +
          translationNote +
          '<div class="sefaria-commentary-body mt-1">' + displayText + '</div>' +
          '<p class="sefaria-attribution"><a href="' + sefariaUrl + '" target="_blank" rel="noopener noreferrer">' + uiMessage('view_on_sefaria') + '</a></p>' +
          '</div>'
        );
      }

      if (cachedCommentary) {
        var cached = cachedCommentary;
        renderCommentaryText(cached.text, cached.url, cached.machine);
        return;
      }

      // Try v3 API first (works for simple-structured commentaries like Rashi)
      $.ajax({
        url: 'https://www.sefaria.org/api/v3/texts/' + encodeURIComponent(fullRef) + '?version=english',
        type: 'GET',
        success: function(data) {
          var versions = (data && data.versions) ? data.versions : [];
          var text = '';
          if (versions.length > 0 && versions[0].text) {
            text = sefariaExtractText(versions[0].text);
          }
          if (text) {
            var sefariaUrl = 'https://www.sefaria.org/' + encodeURIComponent(fullRef).replace(/%20/g, '_');
            translateCommentaryText(text, function(translatedText, isMachineTranslated) {
              setCommentaryCachedValue(sefariaTextCache, 'sefaria_text', fullRef, { text: translatedText, url: sefariaUrl, machine: isMachineTranslated });
              renderCommentaryText(translatedText, sefariaUrl, isMachineTranslated);
            });
          } else {
            $textDiv.html('<p class="sefaria-no-result"><em>' + uiMessage('no_english_text_available', { name: escapedName }) + '</em></p>');
          }
        },
        error: function(jqXHR) {
          // If v3 fails (e.g., complex-structured books), try v2 API as fallback
          console.log('[Sefaria] v3 API failed for "' + fullRef + '", trying v2 fallback');
          $.ajax({
            url: 'https://www.sefaria.org/api/texts/' + encodeURIComponent(fullRef) + '?version=english',
            type: 'GET',
            success: function(data2) {
              var text = '';
              if (data2 && data2.text) {
                text = sefariaExtractText(data2.text);
              }
              if (text) {
                var sefariaUrl = 'https://www.sefaria.org/' + encodeURIComponent(fullRef).replace(/%20/g, '_');
                translateCommentaryText(text, function(translatedText, isMachineTranslated) {
                  setCommentaryCachedValue(sefariaTextCache, 'sefaria_text', fullRef, { text: translatedText, url: sefariaUrl, machine: isMachineTranslated });
                  renderCommentaryText(translatedText, sefariaUrl, isMachineTranslated);
                });
              } else {
                $textDiv.html('<p class="sefaria-no-result"><em>' + uiMessage('no_english_text_available', { name: escapedName }) + '</em></p>');
              }
            },
            error: function(jqXHR2) {
              console.log('[Sefaria] Both v3 and v2 APIs failed for "' + fullRef + '"');
              // Check if it's a complex-structured book error
              var errorResponse = '';
              try {
                errorResponse = jqXHR2.responseJSON && jqXHR2.responseJSON.error ? jqXHR2.responseJSON.error : '';
              } catch(e) {}
              
              if (errorResponse.indexOf('complex') !== -1 || jqXHR2.status === 400 || jqXHR2.status === 404) {
                // For complex-structured books, provide a link to view on Sefaria
                var sefariaUrl = 'https://www.sefaria.org/' + encodeURIComponent(fullRef).replace(/%20/g, '_');
                $textDiv.html(
                  '<p class="sefaria-no-result"><em>' + uiMessage('complex_structure_on_sefaria', { name: escapedName }) + '<br>' +
                  '<a href="' + sefariaUrl + '" target="_blank" rel="noopener noreferrer" style="color:#5c4a1e;">' + uiMessage('view_on_sefaria') + '</a></em></p>'
                );
              } else {
                $textDiv.html('<p class="sefaria-no-result"><em>' + uiMessage('could_not_load_commentary_text', { name: escapedName }) + '</em></p>');
              }
            }
          });
        }
      });
    });

    // ----- Sefaria Jewish Commentary END ------ \\

  });