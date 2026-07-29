(function(global) {
  function sharedOriginalWordTitle(word) {
    if (!word) {
      return '';
    }
    var parts = [];
    if (word.text) {
      parts.push(String(word.text));
    }
    if (word.translation_label) {
      parts.push(String(word.translation_label));
    }
    if (word.grammar) {
      parts.push(String(word.grammar));
    }
    return parts.join(' • ');
  }

  function sharedOriginalWordTranslation(word, fallbackLabel) {
    if (!word) {
      return '';
    }
    var label = String(word.translation_label || '').trim();
    if (label) {
      return label;
    }
    return String(fallbackLabel || '').trim();
  }

  function sharedOriginalFlattenReferences(referenceGroups) {
    var flat = [];
    (referenceGroups || []).forEach(function(group) {
      (group || []).forEach(function(reference) {
        var normalized = String(reference || '').trim();
        if (normalized) {
          flat.push(normalized);
        }
      });
    });
    return flat;
  }

  function sharedOriginalFirstReference(referenceGroups) {
    var flattened = sharedOriginalFlattenReferences(referenceGroups);
    return flattened.length ? flattened[0] : '';
  }

  function sharedOriginalFirstParseableReference(references, parseReference) {
    var parser = typeof parseReference === 'function' ? parseReference : function() { return null; };
    for (var index = 0; index < (references || []).length; index += 1) {
      var reference = String(references[index] || '').trim();
      if (reference && parser(reference)) {
        return reference;
      }
    }
    return '';
  }

  function sharedOriginalFirstReferenceForCandidate(candidate, parseReference) {
    if (!candidate) {
      return '';
    }
    var translationCounts = (candidate.translation_counts || []);
    for (var index = 0; index < translationCounts.length; index += 1) {
      var reference = sharedOriginalFirstReference((translationCounts[index] && translationCounts[index].reference_groups) || []);
      if (reference) {
        return reference;
      }
    }
    var groupedReference = sharedOriginalFirstReference((candidate.reference_groups || []));
    if (groupedReference) {
      return groupedReference;
    }
    return sharedOriginalFirstParseableReference(candidate.references || [], parseReference);
  }

  function sharedOriginalNormalizeStrongsCode(value) {
    var code = String(value || '').toUpperCase().replace(/[{}\[\](),.;:]/g, '').trim();
    return code.replace(/^([GH])0+(\d+)/, function(_, prefix, digits) {
      return prefix + String(parseInt(digits, 10));
    });
  }

  function sharedOriginalUsageOutlineCount(items) {
    var total = 0;
    (items || []).forEach(function(item) {
      total += parseInt((item && item.count) || 0, 10) || 0;
      total += sharedOriginalUsageOutlineCount((item && item.children) || []);
    });
    return total;
  }

  global.WAJOriginalTextShared = global.WAJOriginalTextShared || {
    buildWordTitle: sharedOriginalWordTitle,
    buildWordTranslation: sharedOriginalWordTranslation,
    flattenReferences: sharedOriginalFlattenReferences,
    firstReference: sharedOriginalFirstReference,
    firstParseableReference: sharedOriginalFirstParseableReference,
    firstReferenceForCandidate: sharedOriginalFirstReferenceForCandidate,
    normalizeStrongsCode: sharedOriginalNormalizeStrongsCode,
    usageOutlineCount: sharedOriginalUsageOutlineCount
  };
})(window);

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
  var detailOriginalTextCache = {};
  var translationCache = {};
  var SCRIPTURA_CHAPTER_CACHE_VERSION = 'v2';

  // Manual per-commentator display configuration for Scriptura panel UI.
  var scripturaUiConfig = {
    commentatorAttribution: {
      'david-stern': {
        showProvider: false,
        showApiResponse: false
      },
      'matthew-henry': {
        showProvider: true,
        showApiResponse: true
      }
    }
  };

  function setupNativeComboForSelect($select) {
    if (!$select || !$select.length) {
      return;
    }
    if ($select.prop('multiple')) {
      return;
    }
    if ($select.closest('.bible-study-select-wrap').length) {
      return;
    }

    var $wrap = $select.closest('.select');
    if (!$wrap.length) {
      return;
    }

    var selectId = String($select.attr('id') || '');
    if (!selectId) {
      return;
    }

    var liveSearchAttr = String($select.attr('data-live-search') || '').toLowerCase();
    var liveSearch = liveSearchAttr === 'true' || liveSearchAttr === '1';
    var $input = $wrap.children('.native-combo-input[data-select-id="' + selectId + '"]');
    var $menu = $wrap.children('.native-combo-menu[data-select-id="' + selectId + '"]');

    function closeMenu() {
      $wrap.removeClass('native-combo-open');
      syncInputValue();
    }

    function renderMenu(filterText) {
      var typed = filterText;
      if (typeof typed === 'undefined') {
        typed = $input.val();
      }
      typed = $.trim(String(typed || '')).toLowerCase();
      var selectedValue = String($select.val() || '');
      var items = [];

      $select.find('option').each(function() {
        var optionValue = String($(this).val() || '');
        var label = $.trim($(this).text());
        if (!optionValue || !label) {
          return;
        }
        if (liveSearch && typed && label.toLowerCase().indexOf(typed) === -1) {
          return;
        }
        items.push({ value: optionValue, label: label });
      });

      $menu.empty();
      if (!items.length) {
        $menu.append('<div class="native-combo-empty">No matching option found.</div>');
        return;
      }

      $.each(items, function(_, item) {
        var $item = $('<button type="button" class="native-combo-option"></button>')
          .attr('data-value', item.value)
          .toggleClass('active', item.value === selectedValue)
          .text(item.label);
        $menu.append($item);
      });
    }

    function syncInputValue() {
      var selectedLabel = $.trim($select.find('option:selected').text());
      $input.val(selectedLabel);
      $input.prop('disabled', !!$select.prop('disabled'));
      renderMenu('');
    }

    function closeOpenNativeCombos($exceptWrap) {
      $('.select.native-combo-open').not($exceptWrap || $()).each(function() {
        var $openWrap = $(this);
        var $openSelect = $openWrap.children('select').first();
        var $openInput = $openWrap.children('.native-combo-input').first();
        var selectedLabel = $.trim($openSelect.find('option:selected').text());
        $openInput.val(selectedLabel);
        $openWrap.removeClass('native-combo-open');
      });
    }

    function openMenu() {
      if ($select.prop('disabled')) {
        return;
      }
      closeOpenNativeCombos($wrap);
      renderMenu('');
      $wrap.addClass('native-combo-open');

      if (liveSearch) {
        window.setTimeout(function() {
          $input.trigger('select');
        }, 0);
      }
    }

    if (!$input.length) {
      $input = $('<input type="search" class="native-combo-input" autocomplete="off">')
        .attr('data-select-id', selectId)
        .insertAfter($select);

      if (!liveSearch) {
        $input.prop('readonly', true);
      }

      $input.on('focus click', function() {
        openMenu();
      });

      $input.on('input', function() {
        if (!liveSearch) {
          return;
        }
        var typed = $.trim(String($input.val() || '')).toLowerCase();
        var selectedValue = '';
        $select.find('option').each(function() {
          var optionValue = String($(this).val() || '');
          if (!optionValue || selectedValue) {
            return;
          }
          var label = $.trim($(this).text()).toLowerCase();
          if (typed && (label === typed || label.indexOf(typed) === 0)) {
            selectedValue = optionValue;
          }
        });
        if (selectedValue) {
          $select.val(selectedValue).trigger('change');
        }
        renderMenu();
        $wrap.addClass('native-combo-open');
      });

      $input.on('keydown', function(event) {
        if (event.key === 'Escape') {
          closeMenu();
          return;
        }
        if (event.key === 'ArrowDown') {
          event.preventDefault();
          openMenu();
        }
      });
    }

    if (!$menu.length) {
      $menu = $('<div class="native-combo-menu"></div>')
        .attr('data-select-id', selectId)
        .insertAfter($input);

      $menu.on('mousedown', '.native-combo-option', function(event) {
        event.preventDefault();
        var value = String($(this).attr('data-value') || '');
        if (!value) {
          return;
        }
        $select.val(value).trigger('change');
        syncInputValue();
        closeMenu();
      });
    }

    $wrap.addClass('native-combo-enabled');
    syncInputValue();
  }

  function initStyledNativeSelectCombos() {
    if ($.fn && $.fn.selectpicker) {
      return;
    }

    $('.select select').each(function() {
      setupNativeComboForSelect($(this));
    });

    $(document).off('mousedown.jcNativeCombo').on('mousedown.jcNativeCombo', function(event) {
      if ($(event.target).closest('.select.native-combo-enabled').length) {
        return;
      }
      $('.select.native-combo-open').each(function() {
        var $openWrap = $(this);
        var $openSelect = $openWrap.children('select').first();
        var $openInput = $openWrap.children('.native-combo-input').first();
        var selectedLabel = $.trim($openSelect.find('option:selected').text());
        $openInput.val(selectedLabel);
        $openWrap.removeClass('native-combo-open');
      });
    });

    $(document).off('jc:native-select-refresh.jcNativeCombo').on('jc:native-select-refresh.jcNativeCombo', 'select', function() {
      setupNativeComboForSelect($(this));
    });
  }

  function ensureMinimumVisibleSelectItems() {
    $('select').each(function() {
      var $select = $(this);
      var dataSize = parseInt(String($select.attr('data-size') || ''), 10);
      if ((isNaN(dataSize) || dataSize < 10) && ($select.hasClass('selectpicker') || $select.hasClass('law-filter-select'))) {
        $select.attr('data-size', '10');
      }

      if ($.fn && $.fn.selectpicker && $select.data('selectpicker')) {
        $select.selectpicker('refresh');
      }
    });
  }

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
    // Hide the line breaks around the now-hidden "Study this passage" button.
    $link.prev('br').hide();
    $link.nextAll('br').first().hide();
    $link.hide();
    return true;
  }

  function currentBibleCopyAbbreviation() {
    var selectedAbbreviation = $.trim(String($('#drpBibleTranslation option:selected').data('abbreviation') || ''));
    if (selectedAbbreviation) {
      return selectedAbbreviation.toUpperCase();
    }

    var selectedText = $.trim($('#drpBibleTranslation option:selected').text() || '');
    if (!selectedText) {
      return '';
    }
    var parts = selectedText.split(' - ');
    if (parts.length >= 2 && $.trim(parts[1])) {
      return $.trim(parts[1]).toUpperCase();
    }
    return selectedText.toUpperCase();
  }

  function cleanVerseReferenceLabel(rawText) {
    var text = $.trim(String(rawText || '').replace(/\s+/g, ' '));
    text = text.replace(/^(study this passage on the bible study page|bestudeer deze passage op de bijbelstudie-pagina)\s*:?\s*/i, '');
    text = text.replace(/^:\s*/, '');
    return $.trim(text);
  }

  function extractVerseReferenceLabel($element) {
    var refId = String($element.attr('data-verse-ref') || '').trim();
    var $context = $element.closest('li, .our-services-text, .tab-pane, .card, .media, p, div');
    var $loadLink = refId ? $context.find('.bible-verse-load-link[data-verse-ref="' + refId + '"]').first() : $();
    if ($loadLink.length) {
      var linkText = cleanVerseReferenceLabel($loadLink.text());
      if (linkText) {
        return linkText;
      }
    }

    var $bold = $element.prevAll('b, strong').first();
    if ($bold.length) {
      var boldText = cleanVerseReferenceLabel($bold.text());
      if (boldText) {
        return boldText;
      }
    }

    return '';
  }

  function copyFooterForVerseElement($element) {
    var abbreviation = currentBibleCopyAbbreviation();
    var footer = $.trim(extractVerseReferenceLabel($element));
    if (footer && abbreviation) {
      footer += ' (' + abbreviation + ')';
    }
    return footer;
  }

  function cleanRenderedVerseText(text) {
    return String(text || '')
      .replace(/\r\n?/g, '\n')
      .replace(/\u00b6/g, '')
      .split('\n')
      .map(function(line) { return $.trim(line); })
      .filter(function(line) { return line.length > 0; })
      .join('\n');
  }

  function renderVerseText($elements, text) {
    var cleanText = cleanRenderedVerseText(text);
    $elements.each(function() {
      var $element = $(this);
      var footer = copyFooterForVerseElement($element);
      var $line = $('<span class="bible-verse-text-content js-copy-selectable-line"></span>').text(cleanText);
      if (footer) {
        $line.attr('data-copy-footer', footer);
      }
      $element.empty().append($line);
    });
  }

  function writeCopyText(text, onDone) {
    if (navigator.clipboard && navigator.clipboard.writeText) {
      navigator.clipboard.writeText(text).then(function() {
        if (onDone) onDone(true);
      }).catch(function() {
        if (onDone) onDone(false);
      });
      return;
    }

    var $temp = $('<textarea></textarea>').css({
      left: '-9999px',
      position: 'fixed',
      top: '0'
    }).val(text).appendTo('body');
    $temp.trigger('focus').trigger('select');
    var copied = false;
    try {
      copied = document.execCommand('copy');
    } catch (error) {
      copied = false;
    }
    $temp.remove();
    if (onDone) onDone(copied);
  }

  function ensureCopySelectionBar() {
    if ($('#global-copy-selection-bar').length) {
      return;
    }
    $('body').append(
      '<div id="global-copy-selection-bar" class="copy-selection-bar" hidden>' +
      '<div class="copy-selection-bar-inner">' +
      '<span class="copy-selection-count"></span>' +
      '<div class="copy-selection-actions">' +
      '<button type="button" class="btn btn-sm commentary-action-btn" data-copy-selected-lines="1"><i class="fa fa-copy mr-1" aria-hidden="true"></i>Copy</button>' +
      '<button type="button" class="btn btn-sm commentary-action-btn" data-clear-selected-lines="1"><i class="fa fa-times mr-1" aria-hidden="true"></i>Clear</button>' +
      '</div></div></div>'
    );
  }

  function selectedCopyLines() {
    return $('.js-copy-selectable-line.is-copy-selected');
  }

  function clearSelectedCopyLines() {
    selectedCopyLines().removeClass('is-copy-selected');
    updateCopySelectionBar();
  }

  function updateCopySelectionBar() {
    ensureCopySelectionBar();
    var $bar = $('#global-copy-selection-bar');
    var count = selectedCopyLines().length;
    if (!count) {
      $bar.attr('hidden', true);
      return;
    }
    $bar.find('.copy-selection-count').text(String(count) + ' selected');
    $bar.removeAttr('hidden');
  }

  function buildSelectedCopyText() {
    var $lines = selectedCopyLines();
    if (!$lines.length) {
      return '';
    }

    var firstGroup = $.trim(String($lines.first().attr('data-copy-group') || ''));
    var sameGroup = !!firstGroup;
    $lines.each(function() {
      if ($.trim(String($(this).attr('data-copy-group') || '')) !== firstGroup) {
        sameGroup = false;
        return false;
      }
      return undefined;
    });

    if (sameGroup) {
      var mergedLines = [];
      var verseNumbers = [];
      var first = $lines.first();
      var bookLabel = $.trim(String(first.attr('data-copy-book-label') || ''));
      var chapter = $.trim(String(first.attr('data-copy-chapter') || ''));
      var abbreviation = $.trim(String(first.attr('data-copy-abbreviation') || ''));
      if (!abbreviation && /^bs\|/.test(firstGroup)) {
        var groupParts = firstGroup.split('|');
        var groupBibleId = $.trim(String(groupParts[1] || ''));
        if (groupBibleId) {
          var optionText = $.trim(String($('.bs-bible-select option[value="' + groupBibleId + '"]').first().text() || ''));
          if (optionText) {
            var optionParts = optionText.split(' - ');
            if (optionParts.length >= 2 && $.trim(optionParts[1])) {
              abbreviation = $.trim(optionParts[1]).toUpperCase();
            }
          }
        }
      }

      $lines.each(function() {
        var $line = $(this);
        var copyText = $.trim(String($line.attr('data-copy-text') || $line.text() || ''));
        if (copyText) {
          mergedLines.push(copyText.replace(/\s+/g, ' ').trim());
        }
        var verse = parseInt(String($line.attr('data-copy-verse') || ''), 10);
        if (verse) {
          verseNumbers.push(verse);
        }
      });

      if (mergedLines.length) {
        var mergedText = mergedLines.join(' ').replace(/\s+/g, ' ').trim();
        if (bookLabel && chapter && verseNumbers.length) {
          var startVerse = Math.min.apply(null, verseNumbers);
          var endVerse = Math.max.apply(null, verseNumbers);
          var footer = bookLabel + ' ' + chapter + ':' + startVerse + (endVerse > startVerse ? '-' + endVerse : '');
          if (abbreviation) {
            footer += ' (' + abbreviation + ')';
          }
          return mergedText + '\n\n' + footer;
        }
        return mergedText;
      }
    }

    var chunks = [];
    $lines.each(function() {
      var $line = $(this);
      var lineText = $.trim(String($line.attr('data-copy-text') || $line.text() || ''));
      if (!lineText) {
        return;
      }
      var footer = $.trim(String($line.attr('data-copy-footer') || ''));
      chunks.push(footer ? (lineText + '\n\n' + footer) : lineText);
    });
    return chunks.join('\n\n');
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

  function getBibleStudyUrl() {
    var container = document.querySelector('[data-bible-study-url]');
    return container ? String(container.getAttribute('data-bible-study-url') || '').trim() : '';
  }

  function getOriginalTextUrl() {
    var container = document.querySelector('[data-original-text-url]');
    return container ? String(container.getAttribute('data-original-text-url') || '').trim() : '';
  }

  function bibleStudyBookLookup() {
    return {
      'Genesis': 'Genesis', 'Exodus': 'Exodus', 'Leviticus': 'Leviticus', 'Numbers': 'Numbers', 'Deuteronomy': 'Deuteronomy',
      'Joshua': 'Joshua', 'Judges': 'Judges', 'Ruth': 'Ruth', '1 Samuel': 'SamuelFirstBook', 'I Samuel': 'SamuelFirstBook',
      '2 Samuel': 'SamuelSecondBook', 'II Samuel': 'SamuelSecondBook', '1 Kings': 'KingsFirstBook', 'I Kings': 'KingsFirstBook',
      '2 Kings': 'KingsSecondBook', 'II Kings': 'KingsSecondBook', '1 Chronicles': 'ChroniclesFirstBook', 'I Chronicles': 'ChroniclesFirstBook',
      '2 Chronicles': 'ChroniclesSecondBook', 'II Chronicles': 'ChroniclesSecondBook', 'Ezra': 'Ezra', 'Nehemiah': 'Nehemiah',
      'Esther': 'Esther', 'Job': 'Job', 'Psalms': 'Psalms', 'Proverbs': 'Proverbs', 'Ecclesiastes': 'Ecclesiastes',
      'Song of Solomon': 'SongOfSolomon', 'Song of Songs': 'SongOfSolomon', 'Isaiah': 'Isaiah', 'Jeremiah': 'Jeremiah',
      'Lamentations': 'Lamentations', 'Ezekiel': 'Ezekiel', 'Daniel': 'Daniel', 'Hosea': 'Hosea', 'Joel': 'Joel', 'Amos': 'Amos',
      'Obadiah': 'Obadiah', 'Jonah': 'Jonah', 'Micah': 'Micah', 'Nahum': 'Nahum', 'Habakkuk': 'Habakkuk', 'Zephaniah': 'Zephaniah',
      'Haggai': 'Haggai', 'Zechariah': 'Zechariah', 'Malachi': 'Malachi', 'Matthew': 'Matthew', 'Mark': 'Mark', 'Luke': 'Luke',
      'John': 'John', 'Acts': 'Acts', 'Romans': 'Romans', '1 Corinthians': 'CorinthiansFirstBook', '2 Corinthians': 'CorinthiansSecondBook',
      'Galatians': 'Galatians', 'Ephesians': 'Ephesians', 'Philippians': 'Philippians', 'Colossians': 'Colossians',
      '1 Thessalonians': 'ThessaloniansFirstBook', '2 Thessalonians': 'ThessaloniansSecondBook', '1 Timothy': 'TimothyFirstBook',
      '2 Timothy': 'TimothySecondBook', 'Titus': 'Titus', 'Philemon': 'Philemon', 'Hebrews': 'Hebrews', 'James': 'James',
      '1 Peter': 'PeterFirstBook', '2 Peter': 'PeterSecondBook', '1 John': 'JohnFirstBook', '2 John': 'JohnSecondBook',
      '3 John': 'JohnThirdBook', 'Jude': 'Jude', 'Revelation': 'Revelation'
    };
  }

  function appBookFromDisplayName(name) {
    return bibleStudyBookLookup()[String(name || '').trim()] || '';
  }

  function parseBibleStudyReference(reference) {
    var normalized = String(reference || '').trim();
    if (!normalized) {
      return null;
    }

    var match = normalized.match(/^(.*?)\s+(\d+):(\d+)(?:-(?:(\d+):)?(\d+))?$/);
    if (!match) {
      return null;
    }

    var book = appBookFromDisplayName(match[1]);
    if (!book) {
      return null;
    }

    var chapter = Number(match[2]);
    var startVerse = Number(match[3]);
    var endChapter = match[4] ? Number(match[4]) : chapter;
    var endVerse = match[5] ? Number(match[5]) : startVerse;
    return {
      book: book,
      chapter: chapter,
      startVerse: startVerse,
      endChapter: endChapter,
      endVerse: endVerse
    };
  }

  function buildBibleStudyUrl(details) {
    if (!details || !details.book) {
      return '';
    }

    var baseUrl = getBibleStudyUrl();
    if (!baseUrl) {
      return '';
    }

    var params = new URLSearchParams();
    params.set('book', String(details.book));
    params.set('chapter', String(details.chapter || 1));
    params.set('start_verse', String(details.startVerse || 1));
    params.set('end_verse', String(details.endVerse || details.startVerse || 1));
    if (details.showOriginalText) {
      params.set('show_original', '1');
    }
    if (details.selectedVerse) {
      params.set('selected_verse', String(details.selectedVerse));
    }
    if (details.selectedStrongs) {
      params.set('selected_strongs', String(details.selectedStrongs));
    }
    return baseUrl + '?' + params.toString();
  }

  function shouldRedirectLongPassageToBibleStudy($link) {
    return $link.closest('[data-long-passage-bible-study-only="1"]').length > 0;
  }

  function longPassageVerseLimit($link) {
    var rawValue = String($link.closest('[data-bible-auto-load-verse-limit]').attr('data-bible-auto-load-verse-limit') || '').trim();
    var parsed = parseInt(rawValue, 10);
    if (!isNaN(parsed) && parsed > 0) {
      return parsed;
    }
    return 5;
  }

  function buildLongPassageBibleStudyUrl($link) {
    var $context = $link.closest('li, .our-services-text');
    var details = extractBibleStudyDetails($context);

    // Lesson pages can place the verse label only inside the link text,
    // so fallback to parsing the cleaned label when contextual extraction fails.
    if (!details || !details.book) {
      var fallbackReference = cleanVerseReferenceLabel($link.text());
      var parsedFallback = parseBibleStudyReference(fallbackReference);
      if (parsedFallback && parsedFallback.book) {
        details = parsedFallback;
      }
    }

    if (!details || !details.book) {
      return '';
    }

    var chapter = Number(details.chapter || 1);
    var startVerse = Number(details.startVerse || 1);
    var endChapter = Number(details.endChapter || chapter);
    var endVerse = Number(details.endVerse || startVerse);
    var verseLimit = longPassageVerseLimit($link);
    var cappedEndVerse = startVerse + verseLimit - 1;

    if (endChapter === chapter && endVerse >= startVerse) {
      cappedEndVerse = Math.min(cappedEndVerse, endVerse);
    }

    return buildBibleStudyUrl({
      book: details.book,
      chapter: chapter,
      startVerse: startVerse,
      endVerse: cappedEndVerse
    });
  }

  function updateLongPassageButtonLabels() {
    $('[data-long-passage-bible-study-only="1"] .bible-verse-load-link').each(function() {
      var $link = $(this);
      var referenceLabel = cleanVerseReferenceLabel($link.text());
      var label = uiMessage('study_this_passage_on_bible_study_page');
      if (referenceLabel) {
        label += ': ' + referenceLabel;
      }
      $link.html('<i class="fa fa-book" aria-hidden="true"></i><span class="bible-study-link-label">' + $('<span>').text(label).html() + '</span>');
    });
  }

  function scripturaBookLabelFromKey(book) {
    var mapping = {
      SamuelFirstBook: '1 Samuel', SamuelSecondBook: '2 Samuel', KingsFirstBook: '1 Kings', KingsSecondBook: '2 Kings',
      ChroniclesFirstBook: '1 Chronicles', ChroniclesSecondBook: '2 Chronicles', SongOfSolomon: 'Song of Solomon',
      CorinthiansFirstBook: '1 Corinthians', CorinthiansSecondBook: '2 Corinthians', ThessaloniansFirstBook: '1 Thessalonians',
      ThessaloniansSecondBook: '2 Thessalonians', TimothyFirstBook: '1 Timothy', TimothySecondBook: '2 Timothy',
      PeterFirstBook: '1 Peter', PeterSecondBook: '2 Peter', JohnFirstBook: '1 John', JohnSecondBook: '2 John', JohnThirdBook: '3 John'
    };
    return mapping[String(book || '')] || String(book || '');
  }

  function setCommentaryButtonActive($btn, isActive) {
    if ($btn && $btn.length) {
      $btn.toggleClass('active', !!isActive);
    }
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
    var container = document.querySelector('[data-commentary-language]');
    var pageLanguage = container ? String(container.getAttribute('data-commentary-language') || '').trim().toLowerCase() : '';
    if (pageLanguage) {
      return pageLanguage.slice(0, 2);
    }
    if ($.cookie) {
      var cookieLanguage = String($.cookie('django_language') || '').trim().toLowerCase();
      if (cookieLanguage) {
        return cookieLanguage.slice(0, 2);
      }
    }
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

  function getSwordCommentaryEnabled() {
    var container = document.querySelector('[data-sword-commentary-enabled]');
    return String(container ? container.getAttribute('data-sword-commentary-enabled') : '').trim() === '1';
  }

  function getSwordCommentators() {
    if (!getSwordCommentaryEnabled()) {
      return [];
    }

    var container = document.querySelector('[data-sword-commentators]');
    var rawValue = String(container ? container.getAttribute('data-sword-commentators') : '').trim();
    if (!rawValue) {
      return [];
    }

    try {
      var payload = JSON.parse(rawValue);
      return Array.isArray(payload) ? payload : [];
    } catch (err) {
      console.warn('Could not parse SWORD commentary metadata.', err);
      return [];
    }
  }

  function uiMessage(key, variables) {
    var lang = getCommentaryLanguage() === 'nl' ? 'nl' : 'en';
    var messages = {
      loading_commentary: {
        en: 'Loading commentary...',
        nl: 'Commentaar laden...'
      },
      no_commentary_scriptura_chapter: {
        en: 'No commentary found for this chapter.',
        nl: 'Geen commentaar gevonden voor dit hoofdstuk.'
      },
      no_exact_scriptura_verse: {
        en: 'No exact commentary was found for verse {verse}. Choose an available entry from this chapter.',
        nl: 'Geen exacte toelichting gevonden voor vers {verse}. Kies een beschikbare toelichting uit dit hoofdstuk.'
      },
      other_commentary: {
        en: 'Other Commentary',
        nl: 'Overige Commentaar'
      },
      original_text: {
        en: 'Original text',
        nl: 'Originele tekst'
      },
      study_deeper_in_bible_study_page: {
        en: 'Study deeper in our Bible Study page',
        nl: 'Bestudeer dit dieper op onze Bijbelstudie-pagina'
      },
      select_available_commentary: {
        en: 'Select an available commentary:',
        nl: 'Kies een beschikbare toelichting:'
      },
      could_not_load_scriptura: {
        en: 'Could not load commentary from the configured source.',
        nl: 'Kon commentaar van de geconfigureerde bron niet laden.'
      },
      scriptura_login_required: {
        en: 'Login required to view this commentator.',
        nl: 'Log in om deze commentator te bekijken.'
      },
      select_commentator: {
        en: 'Select a commentator:',
        nl: 'Kies een commentator:'
      },
      no_scriptura_commentators_enabled: {
        en: 'No Scriptura commentators are currently enabled.',
        nl: 'Er zijn momenteel geen Scriptura-commentatoren ingeschakeld.'
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
      },
      original_text_tooltip: {
        en: 'Show the original Hebrew or Greek text with an interactive Strong\'s lexicon.',
        nl: 'Toon de originele Hebreeuwse of Griekse tekst met een interactief Strong\'s lexicon.'
      },
      other_commentary_tooltip: {
        en: 'Open commentary from Lightfoot, King, or other available commentators.',
        nl: 'Open commentaar van Statenvertaling kanttekeningen, King of andere beschikbare commentatoren.'
      },
      jewish_commentary_tooltip: {
        en: 'Open Jewish commentary from Sefaria for this Old Testament passage.',
        nl: 'Open Joods commentaar van Sefaria voor deze Oudtestamentische passage.'
      },
      bible_study_link_tooltip: {
        en: 'Explore this passage in the interactive Bible Study page.',
        nl: 'Verken deze passage op de interactieve Bijbelstudie-pagina.'
      },
      study_this_passage_on_bible_study_page: {
        en: 'Study this passage on the Bible Study page',
        nl: 'Bestudeer deze passage op de Bijbelstudie-pagina'
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

  function getDisabledScripturaCommentatorIds() {
    var container = document.querySelector('[data-scriptura-disabled-commentators]');
    var rawValue = String(container ? container.getAttribute('data-scriptura-disabled-commentators') : '').trim();
    if (!rawValue) {
      return {};
    }
    var disabled = {};
    rawValue.split(',').forEach(function(item) {
      var id = String(item || '').trim().toLowerCase();
      if (id) {
        disabled[id] = true;
      }
    });
    return disabled;
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

  function getDavidSternCommentaryFooterText($contextPanel) {
    var rawValue = '';
    if ($contextPanel && $contextPanel.length) {
      rawValue = String(
        $contextPanel.closest('[data-david-stern-commentary-footer]').attr('data-david-stern-commentary-footer') || ''
      ).trim();
    }
    if (rawValue) {
      return rawValue;
    }
    var container = document.querySelector('[data-david-stern-commentary-footer]');
    return String(container ? container.getAttribute('data-david-stern-commentary-footer') : '').trim();
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

  function sharedOriginalWordTitle(word) {
    var lines = [];
    if (word && word.translation_label) {
      lines.push(String(word.translation_label));
    }
    $.each((word && word.candidates) || [], function(index, candidate) {
      if (index >= 4) {
        return false;
      }
      var gloss = ((candidate && candidate.glosses) || []).slice(0, 3).join(', ');
      var definition = gloss || String((candidate && candidate.definition) || '');
      lines.push(String((candidate && candidate.strongs_number) || '') + ': ' + definition);
    });
    if (!lines.length && word && word.detail_note) {
      lines.push(String(word.detail_note));
    }
    return lines.join('\n');
  }

  function sharedOriginalWordTranslation(word, emptyLabel) {
    if (!word || !word.clickable) {
      return '';
    }
    if (word.translation_label) {
      return String(word.translation_label);
    }
    return String(emptyLabel || '');
  }

  function sharedOriginalFlattenReferences(referenceGroups) {
    return (referenceGroups || []).reduce(function(all, group) {
      (group || []).forEach(function(reference) {
        if (reference) {
          all.push(reference);
        }
      });
      return all;
    }, []);
  }

  function sharedOriginalFirstReference(referenceGroups) {
    var references = sharedOriginalFlattenReferences(referenceGroups);
    return references.length ? String(references[0]) : '';
  }

  function sharedOriginalFirstParseableReference(references, parseReference) {
    for (var index = 0; index < (references || []).length; index += 1) {
      var reference = $.trim(String(references[index] || ''));
      if (reference && (!parseReference || parseReference(reference))) {
        return reference;
      }
    }
    return '';
  }

  function sharedOriginalFirstReferenceForCandidate(candidate, parseReference) {
    if (!candidate) {
      return '';
    }
    var translationCounts = (candidate.translation_counts || []);
    for (var index = 0; index < translationCounts.length; index += 1) {
      var reference = sharedOriginalFirstReference((translationCounts[index] && translationCounts[index].reference_groups) || []);
      if (reference) {
        return reference;
      }
    }
    var groupedReference = sharedOriginalFirstReference((candidate.reference_groups || []));
    if (groupedReference) {
      return groupedReference;
    }
    return sharedOriginalFirstParseableReference(candidate.references || [], parseReference);
  }

  function sharedOriginalNormalizeStrongsCode(value) {
    var code = String(value || '').toUpperCase().replace(/[{}\[\](),.;:]/g, '').trim();
    return code.replace(/^([GH])0+(\d+)/, function(_, prefix, digits) {
      return prefix + String(parseInt(digits, 10));
    });
  }

  function sharedOriginalUsageOutlineCount(items) {
    var total = 0;
    (items || []).forEach(function(item) {
      total += parseInt((item && item.count) || 0, 10) || 0;
      total += sharedOriginalUsageOutlineCount((item && item.children) || []);
    });
    return total;
  }

  window.WAJOriginalTextShared = {
    buildWordTitle: sharedOriginalWordTitle,
    buildWordTranslation: sharedOriginalWordTranslation,
    flattenReferences: sharedOriginalFlattenReferences,
    firstReference: sharedOriginalFirstReference,
    firstParseableReference: sharedOriginalFirstParseableReference,
    firstReferenceForCandidate: sharedOriginalFirstReferenceForCandidate,
    normalizeStrongsCode: sharedOriginalNormalizeStrongsCode,
    usageOutlineCount: sharedOriginalUsageOutlineCount
  };

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
        DIV: true,
      EM: true,
      I: true,
        P: true,
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

  function sanitizeScripturaCommentaryHtml(rawHtml) {
    if (!rawHtml) {
      return '';
    }

    var normalized = String(rawHtml || '')
      .replace(/&lt;\/?\s*scripref\b[^&]*&gt;/gi, '')
      .replace(/<\/?\s*scripref\b[^>]*>/gi, '')
      .replace(/\r\n/g, '\n')
      .replace(/\r/g, '\n')
      .replace(/<br\s*\/?>\s*(<br\s*\/?>\s*)+/gi, '<br><br>');

    var safeHtml = sanitizeSefariaHtml(normalized);
    if (!safeHtml) {
      return '';
    }

    safeHtml = safeHtml
      .replace(/\s*<br\s*\/?>\s*/gi, '<br>')
      .replace(/(?:<br>\s*){3,}/gi, '<br><br>')
      .replace(/^[\s\n]*(<br>\s*)+/i, '')
      .replace(/(<br>\s*)+[\s\n]*$/i, '');

    return safeHtml.trim();
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
    initStyledNativeSelectCombos();
    ensureMinimumVisibleSelectItems();

  updateLongPassageButtonLabels();

  $(document).on('click', '.bible-verse-load-link', function(event) {
    event.preventDefault();
    var $link = $(this);
    var pk = String($link.attr('data-verse-ref') || '').trim();

    if (shouldRedirectLongPassageToBibleStudy($link)) {
      var bibleStudyUrl = buildLongPassageBibleStudyUrl($link);
      if (bibleStudyUrl) {
        window.location.href = bibleStudyUrl;
        return;
      }
    }

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

  $(document).on('click', '.js-copy-selectable-line', function(event) {
    event.preventDefault();
    var $line = $(this);
    if (!$line.text()) {
      return;
    }
    $line.toggleClass('is-copy-selected');
    updateCopySelectionBar();
  });

  $(document).on('click', '[data-clear-selected-lines="1"]', function(event) {
    event.preventDefault();
    clearSelectedCopyLines();
  });

  $(document).on('click', '[data-copy-selected-lines="1"]', function(event) {
    event.preventDefault();
    var copyText = buildSelectedCopyText();
    if (!copyText) {
      return;
    }
    writeCopyText(copyText, function(copied) {
      if (!copied) {
        return;
      }
      clearSelectedCopyLines();
    });
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
      var builtInCommentators = [
        {
          id: 'david-stern',
          label: 'David Stern',
          apiSources: ['david-stern', 'david_stern', 'jnt-stern', 'jnt_stern'],
          autoTranslate: true,
          sourceType: 'scriptura',
          supportsOldTestament: false,
          attribution: scripturaUiConfig.commentatorAttribution['david-stern'] || { showProvider: true, showApiResponse: true }
        }
      ];

      if (isDutch) {
        builtInCommentators.push({
          id: 'matthew-henry',
          label: 'Matthew Henry (NL)',
          apiSources: ['matthew_henry_nl', 'matthew-henry-nl', 'matthew_henry', 'matthew-henry'],
          autoTranslate: false,
          sourceType: 'scriptura',
          supportsOldTestament: true,
          attribution: scripturaUiConfig.commentatorAttribution['matthew-henry'] || { showProvider: true, showApiResponse: true }
        });
      }

      var swordCommentators = getSwordCommentators().map(function(item) {
        var sourceId = String(item.id || '').trim();
        var supportsOldTestament = typeof item.supports_old_testament === 'boolean' ? item.supports_old_testament : true;
        var supportsNewTestament = typeof item.supports_new_testament === 'boolean' ? item.supports_new_testament : true;
        var availableBookKeys = Array.isArray(item.available_book_keys)
          ? item.available_book_keys.map(function(key) { return normalizeCommentaryBookKey(key); }).filter(Boolean)
          : [];
        return {
          id: sourceId,
          label: String(item.label || sourceId),
          apiSources: Array.isArray(item.api_sources) && item.api_sources.length ? item.api_sources : [sourceId],
          autoTranslate: !!item.auto_translate,
          sourceType: 'sword',
          supportsOldTestament: supportsOldTestament,
          supportsNewTestament: supportsNewTestament,
          availableBookKeys: availableBookKeys,
          attribution: {
            showProvider: false,
            showApiResponse: false,
            footerText: String(item.copyright_text || '').trim()
          }
        };
      }).filter(function(item) {
        return !!item.id;
      });

      var allCommentators = builtInCommentators.concat(swordCommentators);

      var disabled = getDisabledScripturaCommentatorIds();
      return allCommentators.filter(function(commentator) {
        return !disabled[commentator.id];
      });
    }

    function getScripturaCommentatorById(commentatorId) {
      var commentators = getScripturaCommentators();
      for (var i = 0; i < commentators.length; i += 1) {
        if (commentators[i].id === commentatorId) {
          return commentators[i];
        }
      }
      return commentators.length ? commentators[0] : null;
    }

    function isNewTestamentBook(book) {
      var normalized = normalizeCommentaryBookKey(book);
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
        revelation: true,
        corinthiansfirstbook: true,
        corinthianssecondbook: true,
        thessaloniansfirstbook: true,
        thessalonianssecondbook: true,
        timothyfirstbook: true,
        timothysecondbook: true,
        peterfirstbook: true,
        petersecondbook: true,
        johnfirstbook: true,
        johnsecondbook: true,
        johnthirdbook: true
      };
      return !!ntBooks[normalized];
    }

    function normalizeCommentaryBookKey(book) {
      var normalized = String(scripturaBookLabelFromKey(book) || book || '').toLowerCase().replace(/[^a-z0-9]/g, '');
      return normalized;
    }

    function commentatorSupportsBook(commentator, book) {
      if (!commentator) {
        return false;
      }
      var normalizedBook = normalizeCommentaryBookKey(book);
      if (!normalizedBook) {
        return true;
      }

      var isNtBook = isNewTestamentBook(book);
      if (!isNtBook && commentator.supportsOldTestament === false) {
        return false;
      }
      if (isNtBook && commentator.supportsNewTestament === false) {
        return false;
      }

      if (Array.isArray(commentator.availableBookKeys) && commentator.availableBookKeys.length > 0) {
        return commentator.availableBookKeys.indexOf(normalizedBook) !== -1;
      }

      return true;
    }

    function availableScripturaCommentatorsForBook(book) {
      return getScripturaCommentators().filter(function(commentator) {
        return commentatorSupportsBook(commentator, book);
      });
    }

    function getDefaultScripturaCommentatorId(book) {
      var commentators = availableScripturaCommentatorsForBook(book);

      if (isNewTestamentBook(book)) {
        for (var i = 0; i < commentators.length; i += 1) {
          if (commentators[i].id === 'david-stern') {
            return 'david-stern';
          }
        }
      } else {
        for (var j = 0; j < commentators.length; j += 1) {
          if (commentators[j].sourceType === 'sword') {
            return commentators[j].id;
          }
        }
      }

      for (var k = 0; k < commentators.length; k += 1) {
        if (commentators[k].supportsOldTestament) {
          return commentators[k].id;
        }
      }

      return commentators.length ? commentators[0].id : '';
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
      var lastErrorMessage = '';

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
          if (onError) onError(lastErrorMessage);
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
          error: function(jqXHR) {
            if (jqXHR && jqXHR.status === 403) {
              lastErrorMessage = uiMessage('scriptura_login_required');
            }
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

    function buildScripturaSourceButtons(activeCommentatorId, book) {
      var commentators = availableScripturaCommentatorsForBook(book);
      var html = '<div class="scriptura-commentary-sources">' +
        '<p class="sefaria-select-label">' + uiMessage('select_commentator') + '</p>';

      commentators.forEach(function(commentator) {
        var activeClass = commentator.id === activeCommentatorId ? ' active' : '';
        html += '<button class="btn btn-sm sefaria-commentator-btn scriptura-commentary-source-btn mr-1 mb-1' + activeClass + '" data-scriptura-commentator="' + $('<span>').text(commentator.id).html() + '">' +
          $('<span>').text(commentator.label).html() +
          '</button>';
      });

      html += '</div>';
      return html;
    }

    function applyCommentaryButtonLabel($button) {
      var label = uiMessage('other_commentary');
      if (!$button || !$button.length) {
        return;
      }
      var textNodes = $button.contents().filter(function() {
        return this.nodeType === 3 && $.trim(this.nodeValue).length;
      });
      if (textNodes.length) {
        textNodes.last()[0].nodeValue = ' ' + label;
      } else {
        $button.append(document.createTextNode(' ' + label));
      }
    }

    function extractBibleStudyDetails($context) {
      var $scriptura = $context.find('.scriptura-commentary-btn').first();
      var referenceLabel = $.trim($context.find('b').first().text());
      var parsedReference = parseBibleStudyReference(referenceLabel);
      if (parsedReference && parsedReference.book) {
        return parsedReference;
      }

      if ($scriptura.length) {
        return {
          book: appBookFromDisplayName($scriptura.data('scriptura-book')),
          chapter: Number($scriptura.data('scriptura-chapter') || 1),
          startVerse: Number($scriptura.data('scriptura-verse') || 1),
          endChapter: Number($scriptura.data('scriptura-chapter') || 1),
          endVerse: Number($scriptura.data('scriptura-verse') || 1)
        };
      }

      var $sefaria = $context.find('.sefaria-commentary-btn-secondary').first();
      if ($sefaria.length) {
        return parseBibleStudyReference($sefaria.data('sefaria-ref'));
      }

      return null;
    }

    function buildBibleStudyAnchor(details, label, showOriginalText) {
      var payload = $.extend({}, details || {});
      payload.showOriginalText = !!showOriginalText;
      var href = buildBibleStudyUrl(payload);
      if (!href) {
        return $();
      }
      return $('<a>', {
        'class': 'detail-bible-study-link',
        href: href,
        title: uiMessage('study_deeper_in_bible_study_page')
      }).text(label || '');
    }

    function enhanceDetailBibleStudyLinks() {
      $('.scriptura-commentary-btn').each(function() {
        applyCommentaryButtonLabel($(this));
      });

      $('.scriptura-commentary-btn, .sefaria-commentary-btn-secondary').each(function() {
        var $seed = $(this);
        var $context = $seed.closest('li, .our-services-text');
        if (!$context.length || $context.closest('.bible-study-shell').length || $context.data('jcBibleStudyEnhanced')) {
          return;
        }

        var details = extractBibleStudyDetails($context);
        if (!details || !details.book) {
          return;
        }

        $context.data('jcBibleStudyEnhanced', true);

        var $reference = $context.find('b').first();
        var referenceLabel = $.trim($reference.text());
        var $verseTarget = $context.find('.bible-verse-load-link, .bible-verse-text').first();
        var hasScripturaForBook = availableScripturaCommentatorsForBook(details.book).length > 0;

        if (!hasScripturaForBook) {
          $context.find('.scriptura-commentary-btn').remove();
          $context.find('.scriptura-commentary-panel').remove();
        }

        var $actionButtons = $context.find('.scriptura-commentary-btn, .sefaria-commentary-btn-secondary').filter(function() {
          return !$(this).hasClass('bible-verse-load-link');
        });

        if (hasScripturaForBook && !$context.find('.scriptura-commentary-btn').length) {
          var $scripturaBtn = $('<button type="button" class="btn btn-sm btn-outline-secondary sefaria-commentary-btn scriptura-commentary-btn"></button>');
          $scripturaBtn.attr('data-scriptura-book', scripturaBookLabelFromKey(details.book));
          $scripturaBtn.attr('data-scriptura-chapter', details.chapter);
          $scripturaBtn.attr('data-scriptura-verse', details.startVerse);
          $scripturaBtn.append('<span class="commentary-inline-icon" aria-hidden="true"><svg class="commentary-inline-icon-svg" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" focusable="false"><path d="M4 19.5v-15A2.5 2.5 0 0 1 6.5 2H19a1 1 0 0 1 1 1v18a1 1 0 0 1-1 1H6.5a1 1 0 0 1 0-5H20"></path></svg></span>');
          applyCommentaryButtonLabel($scripturaBtn);
          $scripturaBtn.appendTo($context);

          // OT blocks can have only a Sefaria panel by default; add Scriptura panel on demand.
          if (!$context.find('.scriptura-commentary-panel').length) {
            $('<div class="scriptura-commentary-panel"></div>').appendTo($context);
          }
        }

        if (!$context.find('.detail-original-text-btn').length) {
          var $origBtn = $('<button>', {
            type: 'button',
            'class': 'btn btn-sm commentary-action-btn detail-original-text-btn jc-tooltip-host'
          })
            .attr('data-bible-study-book', details.book)
            .attr('data-bible-study-chapter', details.chapter)
            .attr('data-bible-study-start-verse', details.startVerse)
            .attr('data-bible-study-end-verse', details.endVerse)
            .attr('data-jc-tooltip', uiMessage('original_text_tooltip'))
            .appendTo($context);
          $origBtn.append('<i class="fa fa-language mr-1" aria-hidden="true"></i>');
          $origBtn.append(document.createTextNode(uiMessage('original_text')));
        }

        if (!$context.find('.detail-inline-original-panel').length) {
          $('<div class="detail-inline-original-panel"></div>').appendTo($context);
        }

        $actionButtons = $context.find('.scriptura-commentary-btn, .sefaria-commentary-btn-secondary, .detail-original-text-btn').filter(function() {
          return !$(this).hasClass('bible-verse-load-link');
        });

        if ($reference.length && referenceLabel && $actionButtons.length) {
          var $row = $('<div class="bible-reference-action-row"></div>');
          var $link = buildBibleStudyAnchor(details, referenceLabel, false);
          if ($link.length) {
            $link.attr('data-jc-tooltip', uiMessage('bible_study_link_tooltip')).addClass('jc-tooltip-host');
            $row.append($link);
          }
          $actionButtons.each(function() {
            var $btn = $(this);
            if (!$btn.data('jcTooltipSet')) {
              var tooltip = '';
              if ($btn.hasClass('scriptura-commentary-btn')) {
                tooltip = uiMessage('other_commentary_tooltip');
              } else if ($btn.hasClass('sefaria-commentary-btn-secondary')) {
                tooltip = uiMessage('jewish_commentary_tooltip');
              } else if ($btn.hasClass('detail-original-text-btn')) {
                tooltip = uiMessage('original_text_tooltip');
              }
              if (tooltip) {
                $btn.attr('data-jc-tooltip', tooltip).addClass('jc-tooltip-host');
              }
              $btn.data('jcTooltipSet', true);
            }
            $row.append(this);
          });
          if ($verseTarget.length) {
            $row.insertBefore($verseTarget.first());
          } else {
            $context.prepend($row);
          }
          $reference.hide();
          $reference.next('br').hide();
        }
      });
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

        var normalizedText = String(rawText || '')
          .replace(/\r\n/g, '\n')
          .replace(/\r/g, '\n')
          .replace(/[ \t]+\n/g, '\n')
          .replace(/\n{3,}/g, '\n\n')
          .trim();

        function commentaryParagraphs(text) {
          var paragraphs = String(text || '')
            .split(/\n{2,}/)
            .map(function(paragraph) {
              return paragraph.trim();
            })
            .filter(Boolean);

          if (paragraphs.length > 1) {
            return paragraphs;
          }

          if (!text || text.length < 240) {
            return [text];
          }

          var sentences = String(text).match(/[^.!?]+[.!?]+(?:\s+|$)|[^.!?]+$/g) || [text];
          if (sentences.length < 3) {
            return [text];
          }

          paragraphs = [];
          var buffer = [];
          var bufferLength = 0;
          $.each(sentences, function(_, sentence) {
            sentence = String(sentence || '').trim();
            if (!sentence) {
              return;
            }

            buffer.push(sentence);
            bufferLength += sentence.length;
            if (buffer.length >= 2 || bufferLength >= 260) {
              paragraphs.push(buffer.join(' '));
              buffer = [];
              bufferLength = 0;
            }
          });

          if (buffer.length) {
            paragraphs.push(buffer.join(' '));
          }

          return paragraphs.length ? paragraphs : [text];
        }

        var containsHtml = /<[^>]+>/.test(String(rawText || ''));
        var displayHtml = containsHtml
          ? sanitizeScripturaCommentaryHtml(rawText)
          : sanitizeSefariaHtml(commentaryParagraphs(normalizedText).map(function(paragraph) {
              return '<p>' + $('<span>').text(paragraph).html().replace(/\n/g, '<br>') + '</p>';
            }).join(''));
        displayHtml = displayHtml || $('<span>').text(normalizedText).html().replace(/\n/g, '<br>');
        var attribution = (commentator && commentator.attribution) ? commentator.attribution : { showProvider: true, showApiResponse: true };
        var translationNote = '';
        if (isMachineTranslated) {
          translationNote = '<p class="sefaria-attribution"><em>' + uiMessage('machine_translated_from_en') + '</em></p>';
        }

        var attributionParts = [];
        if (attribution.showProvider) {
          attributionParts.push('Commentary provided by <a href="https://www.bijbelapi.com/" target="_blank" rel="noopener noreferrer">BijbelAPI</a>');
        }
        if (attribution.showApiResponse) {
          attributionParts.push('<a href="' + scripturaUrl + '" target="_blank" rel="noopener noreferrer">Open API response</a>');
        }
        var footerText = String(attribution.footerText || '').trim();
        if (!footerText && commentator && commentator.id === 'david-stern') {
          footerText = getDavidSternCommentaryFooterText($panel);
        }
        if (footerText) {
          attributionParts.push($('<span>').text(footerText).html());
        }
        var attributionHtml = attributionParts.length ? ('<p class="sefaria-attribution">' + attributionParts.join(' · ') + '</p>') : '';

        $panel.find('.scriptura-commentary-text').html(
          '<div class="sefaria-commentary-content">' +
          '<strong>' + $('<span>').text(sourceLabel).html() + ' · ' + $('<span>').text(titleLabel).html() + '</strong>' +
          translationNote +
          '<div class="sefaria-commentary-body mt-1">' + displayHtml + '</div>' +
          attributionHtml +
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

      function parseVerseNumber(value) {
        var match = String(value || '').match(/\d+/);
        return match ? Number(match[0]) : NaN;
      }

      function pickPreferredEntryKey() {
        var verseNumber = parseVerseNumber(verse);
        var numericKeys = entryKeys.filter(function(key) {
          return String(key) !== '0' && !isNaN(Number(key));
        }).map(function(key) {
          return { key: key, num: Number(key) };
        }).sort(function(a, b) {
          return a.num - b.num;
        });

        if (!isNaN(verseNumber)) {
          if (entries[String(verseNumber)]) {
            return String(verseNumber);
          }
          var candidate = null;
          numericKeys.forEach(function(item) {
            if (item.num <= verseNumber) {
              candidate = item.key;
            }
          });
          if (candidate) {
            return candidate;
          }
        }

        if (numericKeys.length > 0) {
          return numericKeys[0].key;
        }
        if (entryKeys.indexOf('0') !== -1) {
          return '0';
        }
        return entryKeys[0];
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

      var preferredKey = pickPreferredEntryKey();
      renderScripturaEntry($panel, preferredKey, entries[preferredKey], source, book, chapter, endpoint, commentator);
    }

    function loadScripturaCommentaryForCommentator($panel, commentatorId, preferredVerse) {
      var book = $panel.data('scripturaBook');
      var chapter = $panel.data('scripturaChapter');
      var verse = typeof preferredVerse === 'undefined' ? $panel.data('scripturaVerse') : preferredVerse;
      var commentator = getScripturaCommentatorById(commentatorId);
      if (!commentator) {
        $panel.find('.scriptura-commentary-source-content').html('<p class="sefaria-no-result"><em>' + uiMessage('no_scriptura_commentators_enabled') + '</em></p>');
        return;
      }
      var chapterCacheKey = [SCRIPTURA_CHAPTER_CACHE_VERSION, commentator.id, String(book || ''), String(chapter || '')].join('|');
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
      }, function(errorMessage) {
        console.log('[BijbelAPI] Commentary request failed for all configured hosts/sources');
        $panel.find('.scriptura-commentary-source-content').html('<p class="sefaria-no-result"><em>' + (errorMessage || uiMessage('could_not_load_scriptura')) + '</em></p>');
      });
    }

    function resolveCommentaryPanel($btn, panelClass) {
      var $panel = $btn.nextAll(panelClass).first();
      if ($panel.length) {
        return $panel;
      }

      $panel = $btn.closest('li').find(panelClass).first();
      if ($panel.length) {
        return $panel;
      }

      $panel = $btn.closest('.our-services-text').find(panelClass).first();
      if ($panel.length) {
        return $panel;
      }

      return $btn.closest('.bible-study-verse-item, .bible-study-verse-card').find(panelClass).first();
    }

    function detailOriginalCacheKey(details) {
      return [details.book, details.chapter, details.startVerse, details.endVerse].join('|');
    }

    function detailOriginalChunks(details) {
      var chunks = [];
      var startVerse = Number(details.startVerse || 1);
      var endVerse = Number(details.endVerse || startVerse);
      while (startVerse <= endVerse) {
        var chunkEnd = Math.min(endVerse, startVerse + 4);
        chunks.push({
          book: details.book,
          chapter: Number(details.chapter || 1),
          startVerse: startVerse,
          endVerse: chunkEnd
        });
        startVerse = chunkEnd + 1;
      }
      return chunks;
    }

    function detailOriginalFirstSelectableWordIndex(words) {
      for (var index = 0; index < (words || []).length; index += 1) {
        if (words[index] && words[index].clickable) {
          return index;
        }
      }
      return -1;
    }

    function originalTextShared() {
      return window.WAJOriginalTextShared || {};
    }

    function detailOriginalUiText(key) {
      var lang = getCommentaryLanguage() === 'nl' ? 'nl' : 'en';
      var labels = {
        noTagYet: { en: 'No tag yet', nl: 'Nog geen tag' },
        directGloss: { en: 'Direct gloss', nl: 'Directe gloss' },
        grammar: { en: 'Grammar', nl: 'Grammatica' },
        lookupNote: { en: 'Lookup note', nl: 'Opzoeknotitie' },
        normalizedLookup: { en: 'Normalized lookup form', nl: 'Genormaliseerde zoekvorm' },
        strongsDefinitions: { en: 'Strongs Definitions', nl: 'Strongs-definities' },
        rootWord: { en: 'Root Word', nl: 'Wortelwoord' },
        lxxEquivalent: { en: 'Most likely Hebrew equivalent based on Septuagint usage', nl: 'Meest waarschijnlijke Hebreeuwse equivalent op basis van Septuaginta-gebruik' },
        outlineUsage: { en: 'Outline of Biblical Usage', nl: 'Overzicht van Bijbels gebruik' },
        kjvTranslation: { en: 'KJV Translation', nl: 'KJV-vertaling' },
        occurrences: { en: 'Occurrences', nl: 'Voorkomens' },
        sourceTitle: { en: 'Original text', nl: 'Originele tekst' },
        detailTitle: { en: "Strong's details", nl: "Strong's details" },
        hoverWords: { en: 'Hover / click words', nl: 'Beweeg / klik woorden' },
        translate: { en: 'Translate', nl: 'Vertalen' },
        showOriginal: { en: 'Show original', nl: 'Toon origineel' },
        openBlueLetter: { en: 'Open {code} in Blue Letter Bible', nl: 'Open {code} in Blue Letter Bible' },
        previewPassage: { en: 'Preview this passage', nl: 'Bekijk deze passage' },
        noWordData: { en: 'No original-language word data found for this verse.', nl: 'Geen originele woorddata gevonden voor dit vers.' },
        hoverPrompt: { en: 'Hover or click an original-language word to inspect Strong\'s numbers, lemma data, and possible translations.', nl: 'Beweeg over of klik op een woord uit de brontekst om Strong\'s-nummers, lemma-data en mogelijke vertalingen te bekijken.' }
      };
      return (labels[key] && labels[key][lang]) || (labels[key] && labels[key].en) || key;
    }

    function detailOriginalNormalizeStrongsCode(value) {
      return originalTextShared().normalizeStrongsCode(value);
    }

    function detailOriginalStrongDetailUrl(details, strongsNumber) {
      if (!details || !details.book || !strongsNumber) {
        return '';
      }
      return buildBibleStudyUrl({
        book: details.book,
        chapter: details.chapter,
        startVerse: details.startVerse,
        endVerse: details.endVerse,
        showOriginalText: true,
        selectedVerse: details.startVerse,
        selectedStrongs: detailOriginalNormalizeStrongsCode(strongsNumber)
      });
    }

    function detailOriginalFlattenReferences(referenceGroups) {
      return originalTextShared().flattenReferences(referenceGroups);
    }

    function detailOriginalWordTitle(word) {
      return originalTextShared().buildWordTitle(word);
    }

    function detailOriginalWordTranslation(word) {
      return originalTextShared().buildWordTranslation(word, detailOriginalUiText('noTagYet'));
    }

    function detailOriginalEscape(value) {
      return $('<span>').text(String(value || '')).html();
    }

    function detailOriginalReferenceItemsHtml(referenceGroups) {
      return detailOriginalFlattenReferences(referenceGroups).slice(0, 24).map(function(reference) {
        var parsed = parseBibleStudyReference(reference);
        var href = parsed ? buildBibleStudyUrl({
          book: parsed.book,
          chapter: parsed.chapter,
          startVerse: parsed.startVerse,
          endVerse: parsed.endVerse,
          showOriginalText: false
        }) : '';
        if (href) {
          return '<a class="detail-inline-original-ref-item detail-inline-original-ref-link" href="' + detailOriginalEscape(href) + '" title="' + detailOriginalEscape(detailOriginalUiText('previewPassage')) + '">' + detailOriginalEscape(reference) + '</a>';
        }
        return '<span class="detail-inline-original-ref-item">' + detailOriginalEscape(reference) + '</span>';
      }).join('');
    }

    function detailOriginalUsageOutlineCount(items) {
      return originalTextShared().usageOutlineCount(items);
    }

    function detailOriginalUsageOutlineItemsHtml(items) {
      items = (items || []).filter(function(item) {
        return item && (String(item.label || '').trim() || String(item.summary || '').trim() || ((item.children || []).length > 0) || ((item.reference_groups || []).length > 0));
      });
      if (!items.length) {
        return '';
      }

      return '<ol class="detail-inline-original-meaning-list detail-inline-original-usage-outline">' + items.map(function(item) {
        var count = parseInt((item && item.count) || 0, 10) || 0;
        var label = String((item && item.label) || '').trim();
        var summary = String((item && item.summary) || '').trim();
        var grammar = String((item && item.grammar_label) || '').trim();
        var refsHtml = detailOriginalReferenceItemsHtml((item && item.reference_groups) || []);
        var childrenHtml = detailOriginalUsageOutlineItemsHtml((item && item.children) || []);
        return '<li>' +
          (grammar ? '<div class="detail-inline-original-usage-grammar">' + detailOriginalEscape(grammar) + '</div>' : '') +
          (label ? '<span class="detail-inline-original-translatable">' + detailOriginalEscape(label) + '</span>' : '<span>' + detailOriginalEscape(detailOriginalUiText('occurrences')) + '</span>') +
          (count ? ' <span class="detail-inline-original-usage-count">(' + detailOriginalEscape(count) + 'x)</span>' : '') +
          (summary ? '<p class="mb-1 detail-inline-original-translatable">' + detailOriginalEscape(summary) + '</p>' : '') +
          (refsHtml ? '<div class="detail-inline-original-ref-list">' + refsHtml + '</div>' : '') +
          childrenHtml +
        '</li>';
      }).join('') + '</ol>';
    }

    function detailOriginalUsageSectionHtml(candidate) {
      var usageOutline = ((candidate && candidate.usage_outline) || []).filter(function(item) {
        return item && (String(item.label || '').trim() || String(item.summary || '').trim() || ((item.children || []).length > 0) || ((item.reference_groups || []).length > 0));
      });
      var referenceGroups = (candidate && candidate.reference_groups) || [];
      if (!usageOutline.length && !referenceGroups.length) {
        return '';
      }
      var totalCount = usageOutline.length ? detailOriginalUsageOutlineCount(usageOutline) : 0;
      var refsHtml = !usageOutline.length ? detailOriginalReferenceItemsHtml(referenceGroups) : '';
      var contentHtml = usageOutline.length ? detailOriginalUsageOutlineItemsHtml(usageOutline) : '<div class="detail-inline-original-ref-list">' + refsHtml + '</div>';
      return '<div class="detail-inline-original-detail-section"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('outlineUsage')) + (totalCount ? ' (' + detailOriginalEscape(totalCount) + 'x)' : '') + '</small>' + contentHtml + '</div>';
    }

    function detailOriginalRelatedWordCardHtml(item, showUsageOutline, details) {
      var strongsNumber = String((item && (item.strongs_number || item.strong)) || '');
      var meanings = showUsageOutline ? [] : ((item && item.possible_meanings) || []);
      var usageOutline = showUsageOutline ? ((item && item.usage_outline) || []) : [];
      var metaBits = [];
      if (item && item.count) {
        metaBits.push(detailOriginalEscape(item.count) + 'x');
      }
      if (item && item.percentage) {
        metaBits.push(detailOriginalEscape(item.percentage) + '%');
      }
      if (item && item.confidence) {
        metaBits.push('confidence ' + detailOriginalEscape(item.confidence));
      }
      var meaningsHtml = meanings.length
        ? '<ul class="detail-inline-original-meaning-list">' + meanings.map(function(meaning) {
          return '<li>' + detailOriginalEscape(meaning) + '</li>';
        }).join('') + '</ul>'
        : '';
      var usageOutlineHtml = usageOutline.length
        ? '<div class="detail-inline-original-detail-section mb-0"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('outlineUsage')) + '</small>' + detailOriginalUsageOutlineItemsHtml(usageOutline) + '</div>'
        : '';
      var strongsUrl = detailOriginalStrongDetailUrl(details, strongsNumber);
      var blueLetterLabel = detailOriginalUiText('openBlueLetter').replace('{code}', strongsNumber);
      return '<div class="detail-inline-original-root-word">' +
        '<div class="detail-inline-original-candidate-head">' +
          (strongsUrl ? '<a class="detail-inline-original-strong-link" href="' + detailOriginalEscape(strongsUrl) + '"><strong>' + detailOriginalEscape(strongsNumber) + '</strong></a>' : '<strong>' + detailOriginalEscape(strongsNumber) + '</strong>') +
          ((item && item.lemma) ? '<span>' + detailOriginalEscape(item.lemma) + '</span>' : '') +
          ((item && item.transliteration) ? '<span class="text-muted">' + detailOriginalEscape(item.transliteration) + '</span>' : '') +
          (metaBits.length ? '<span class="detail-inline-original-count-badge">' + metaBits.join(' · ') + '</span>' : '') +
          ((item && item.blueletter_url) ? '<a href="' + detailOriginalEscape(item.blueletter_url) + '" target="_blank" rel="noopener noreferrer">' + detailOriginalEscape(blueLetterLabel) + '</a>' : '') +
        '</div>' +
        (!showUsageOutline && item && item.definition ? '<p class="mb-1 detail-inline-original-translatable">' + detailOriginalEscape(item.definition) + '</p>' : '') +
        meaningsHtml +
        usageOutlineHtml +
      '</div>';
    }

    function detailOriginalSentenceHtml(words, languageCode) {
      var sentenceClass = languageCode === 'hbo'
        ? 'detail-inline-original-sentence-words detail-inline-original-language-hbo'
        : 'detail-inline-original-sentence-words detail-inline-original-language-grc';
      return '<div class="' + sentenceClass + '">' + (words || []).map(function(word, index) {
        var tokenText = String((word && (word.sentence_text || word.text)) || '').trim();
        if (!tokenText) {
          return '';
        }
        var clickable = !!(word && word.clickable);
        var languageClass = languageCode === 'hbo' ? ' detail-inline-original-language-hbo' : ' detail-inline-original-language-grc';
        return '<span class="detail-inline-original-token' + languageClass + '" data-word-index="' + $('<span>').text(String(index)).html() + '" data-clickable="' + (clickable ? '1' : '0') + '"' + (clickable ? ' tabindex="0" role="button"' : '') + '>' + $('<span>').text(tokenText).html() + '</span>';
      }).join('') + '</div>';
    }

    function detailOriginalRenderWordDetail($panel, details, versePayload, wordIndex) {
      var words = (versePayload && versePayload.words) || [];
      var selectedWord = (wordIndex >= 0 && wordIndex < words.length) ? words[wordIndex] : null;
      var $detail = $panel.find('.detail-inline-original-detail-body');
      if (!$detail.length) {
        return;
      }

      if (!selectedWord || !selectedWord.clickable) {
        $detail.html('<p class="mb-0 text-muted detail-inline-original-translatable">' + detailOriginalEscape(detailOriginalUiText('hoverPrompt')) + '</p>');
        return;
      }

      var html = '<div class="detail-inline-original-meta"><strong>' + detailOriginalEscape(selectedWord.text || '') + '</strong> · ' + detailOriginalEscape(String((versePayload && versePayload.language_label) || '')) + '</div>';
      if (selectedWord.translation_label) {
        html += '<p class="mb-2"><small>' + detailOriginalEscape(detailOriginalUiText('directGloss')) + ': ' + detailOriginalEscape(selectedWord.translation_label) + '</small></p>';
      }
      if (selectedWord.grammar) {
        html += '<p class="mb-2"><small>' + detailOriginalEscape(detailOriginalUiText('grammar')) + ': <code>' + detailOriginalEscape(selectedWord.grammar) + '</code></small></p>';
      }

      if (!selectedWord.has_candidates) {
        html += '<div class="detail-inline-original-candidate">' +
          '<div class="detail-inline-original-candidate-head"><strong>' + detailOriginalEscape(detailOriginalUiText('lookupNote')) + '</strong></div>' +
          '<p class="mb-1 detail-inline-original-translatable">' + detailOriginalEscape(String(selectedWord.detail_note || '')) + '</p>' +
          (selectedWord.lookup_key ? '<p class="mb-0"><small>' + detailOriginalEscape(detailOriginalUiText('normalizedLookup')) + ': ' + detailOriginalEscape(String(selectedWord.lookup_key)) + '</small></p>' : '') +
        '</div>';
        $detail.html(html);
        detailOriginalMaybeApplyTranslation($panel);
        return;
      }

      $.each(selectedWord.candidates || [], function(_, candidate) {
        var usageHtml = detailOriginalUsageSectionHtml(candidate || {});
        var rootWordsHtml = ((candidate && candidate.root_words) || []).map(function(rootWord) {
          return detailOriginalRelatedWordCardHtml(rootWord || {}, false, details);
        }).join('');
        var lxxHebrewHtml = ((candidate && candidate.lxx_hebrew_equivalents) || []).map(function(item) {
          return detailOriginalRelatedWordCardHtml(item || {}, true, details);
        }).join('');
        var strongsNumber = String((candidate && candidate.strongs_number) || '');
        var strongsUrl = detailOriginalStrongDetailUrl(details, strongsNumber);
        var blueLetterLabel = detailOriginalUiText('openBlueLetter').replace('{code}', strongsNumber);
        html += '<div class="detail-inline-original-candidate">' +
          '<div class="detail-inline-original-candidate-head">' +
          (strongsUrl ? '<a class="detail-inline-original-strong-link" href="' + detailOriginalEscape(strongsUrl) + '"><strong>' + detailOriginalEscape(strongsNumber) + '</strong></a>' : '<strong>' + detailOriginalEscape(strongsNumber) + '</strong>') +
          ((candidate && candidate.lemma) ? '<span>' + detailOriginalEscape(candidate.lemma) + '</span>' : '') +
          ((candidate && candidate.transliteration) ? '<span class="text-muted">' + detailOriginalEscape(candidate.transliteration) + '</span>' : '') +
          '</div>' +
          usageHtml +
          ((candidate && candidate.kjv_definition) ? '<div class="detail-inline-original-detail-section"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('kjvTranslation')) + '</small><p class="mb-0 detail-inline-original-translatable">' + detailOriginalEscape(candidate.kjv_definition) + '</p></div>' : '') +
          ((candidate && candidate.definition) ? '<div class="detail-inline-original-detail-section"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('strongsDefinitions')) + '</small><p class="mb-0 detail-inline-original-translatable">' + detailOriginalEscape(candidate.definition) + '</p></div>' : '') +
          ((rootWordsHtml || (candidate && candidate.derivation)) ? '<div class="detail-inline-original-detail-section"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('rootWord')) + '</small>' + rootWordsHtml + (!rootWordsHtml && candidate && candidate.derivation ? '<p class="mb-0 detail-inline-original-translatable">' + detailOriginalEscape(candidate.derivation) + '</p>' : '') + '</div>' : '') +
          (lxxHebrewHtml ? '<div class="detail-inline-original-detail-section"><small class="font-weight-bold d-block mb-1">' + detailOriginalEscape(detailOriginalUiText('lxxEquivalent')) + '</small>' + lxxHebrewHtml + '</div>' : '') +
          ((candidate && candidate.blueletter_url) ? '<p class="mb-0 mt-2"><small><a href="' + detailOriginalEscape(candidate.blueletter_url) + '" target="_blank" rel="noopener noreferrer">' + detailOriginalEscape(blueLetterLabel) + '</a></small></p>' : '') +
          '</div>';
      });

      $detail.html(html);
      detailOriginalMaybeApplyTranslation($panel);
    }

    function detailOriginalSyncSelection($panel, wordIndex) {
      $panel.find('.detail-inline-original-token, .detail-inline-original-word-btn, .detail-inline-original-word-translation').removeClass('active');
      $panel.find('.detail-inline-original-token[data-word-index="' + wordIndex + '"]').addClass('active');
      $panel.find('.detail-inline-original-word-btn[data-word-index="' + wordIndex + '"]').addClass('active');
      $panel.find('.detail-inline-original-word-translation[data-word-index="' + wordIndex + '"]').addClass('active');
    }

    function detailOriginalSyncHover($panel, wordIndex, hovering) {
      $panel.find('.detail-inline-original-token[data-word-index="' + wordIndex + '"]').toggleClass('is-hovered', !!hovering);
      $panel.find('.detail-inline-original-word-btn[data-word-index="' + wordIndex + '"]').toggleClass('is-hovered', !!hovering);
      $panel.find('.detail-inline-original-word-translation[data-word-index="' + wordIndex + '"]').toggleClass('is-hovered', !!hovering);
    }

    function detailOriginalApplyTranslation($panel) {
      $panel.find('.detail-inline-original-translatable').each(function() {
        var $el = $(this);
        var originalText = String($el.data('originalText') || $el.text() || '');
        if (!$el.data('originalText')) {
          $el.data('originalText', originalText);
        }
        translateCommentaryText(originalText, function(translated) {
          $el.text(translated || originalText);
        });
      });
    }

    function detailOriginalRevertTranslation($panel) {
      $panel.find('.detail-inline-original-translatable').each(function() {
        var $el = $(this);
        if ($el.data('originalText')) {
          $el.text(String($el.data('originalText')));
        }
      });
    }

    function detailOriginalMaybeApplyTranslation($panel) {
      if ($panel.data('detailOriginalTranslated')) {
        detailOriginalApplyTranslation($panel);
      }
    }

    function detailOriginalVerseHtml(details, referenceLabel, verseKey, versePayload) {
      var firstWordIndex = detailOriginalFirstSelectableWordIndex((versePayload && versePayload.words) || []);
      var languageCode = String((versePayload && versePayload.language_code) || '');
      var uiLang = getCommentaryLanguage();
      var translateButtonHtml = uiLang !== 'en'
        ? '<button type="button" class="btn btn-sm btn-outline-secondary detail-inline-original-translate-btn mt-1 mb-1"><i class="fa fa-language mr-1" aria-hidden="true"></i><span class="detail-inline-original-translate-label">' + detailOriginalEscape(detailOriginalUiText('translate')) + '</span></button>'
        : '';
      var wordButtons = ((versePayload && versePayload.words) || []).map(function(word, index) {
        if (!word || !word.clickable) {
          var punctLanguageClass = languageCode === 'hbo' ? ' detail-inline-original-language-hbo' : ' detail-inline-original-language-grc';
          return '<span class="detail-inline-original-word-item' + (languageCode === 'hbo' ? ' detail-inline-original-word-item-hbo' : '') + '"><span class="detail-inline-original-word-strongs"></span><span class="detail-inline-original-word-punct' + punctLanguageClass + '">' + $('<span>').text(String((word && word.text) || '')).html() + '</span><span class="detail-inline-original-word-translation detail-inline-original-word-translation-empty" data-word-index="' + $('<span>').text(String(index)).html() + '"></span></span>';
        }
        var strongsLabel = String((((word.candidates || [])[0] || {}).strongs_number) || '');
        var languageClass = languageCode === 'hbo' ? ' detail-inline-original-language-hbo' : ' detail-inline-original-language-grc';
        return '<span class="detail-inline-original-word-item">' +
          '<span class="detail-inline-original-word-strongs">' + $('<span>').text(strongsLabel).html() + '</span>' +
          '<button type="button" class="detail-inline-original-word-btn' + languageClass + (index === firstWordIndex ? ' active' : '') + (word.has_candidates ? '' : ' detail-inline-original-word-btn-missing') + '" data-word-index="' + $('<span>').text(String(index)).html() + '" title="' + $('<span>').text(detailOriginalWordTitle(word)).html() + '">' + $('<span>').text(String(word.text || '')).html() + '</button>' +
          '<span class="detail-inline-original-word-translation' + (detailOriginalWordTranslation(word) ? '' : ' detail-inline-original-word-translation-empty') + '" data-word-index="' + $('<span>').text(String(index)).html() + '">' + $('<span>').text(detailOriginalWordTranslation(word)).html() + '</span>' +
          '</span>';
      }).join('');

      return '<div class="detail-inline-original-verse" data-verse="' + $('<span>').text(String(verseKey)).html() + '">' +
        '<div class="row">' +
          '<div class="col-lg-6 mb-2">' +
            '<div class="detail-inline-original-sentence">' +
              '<div class="detail-inline-original-head"><span class="detail-inline-original-title">' + detailOriginalEscape(detailOriginalUiText('sourceTitle')) + ' · ' + $('<span>').text(referenceLabel).html() + '</span><span class="badge badge-light border">' + detailOriginalEscape(detailOriginalUiText('hoverWords')) + '</span></div>' +
              '<div class="detail-inline-original-source-badge">' + detailOriginalEscape(String((versePayload && versePayload.source_bible_name) || '')) + '</div>' +
              detailOriginalSentenceHtml((versePayload && versePayload.words) || [], languageCode) +
              '<div class="detail-inline-original-word-cloud">' + (wordButtons || '<p class="mb-0 text-muted">' + detailOriginalEscape(detailOriginalUiText('noWordData')) + '</p>') + '</div>' +
            '</div>' +
          '</div>' +
          '<div class="col-lg-6 mb-2">' +
            '<div class="detail-inline-original-detail">' +
              '<div class="detail-inline-original-head"><span class="detail-inline-original-title">' + detailOriginalEscape(detailOriginalUiText('detailTitle')) + '</span>' + translateButtonHtml + '</div>' +
              '<div class="detail-inline-original-detail-body"></div>' +
            '</div>' +
          '</div>' +
        '</div>' +
      '</div>';
    }

    function detailOriginalApplyPayload($panel, details, payload) {
      var verses = (payload && payload.verses) ? payload.verses : {};
      var html = '<div class="detail-inline-original-grid"></div>';
      $panel.html(html);
      var $grid = $panel.find('.detail-inline-original-grid');
      Object.keys(verses).sort(function(a, b) { return Number(a) - Number(b); }).forEach(function(verseKey) {
        var referenceLabel = scripturaBookLabelFromKey(details.book) + ' ' + details.chapter + ':' + verseKey;
        var versePayload = verses[verseKey] || {};
        var verseDetails = $.extend({}, details, {
          startVerse: Number(verseKey),
          endVerse: Number(verseKey)
        });
        var $verse = $(detailOriginalVerseHtml(verseDetails, referenceLabel, verseKey, versePayload));
        $verse.data('verseDetails', verseDetails);
        $verse.data('versePayload', versePayload);
        $grid.append($verse);
        detailOriginalRenderWordDetail($verse, verseDetails, versePayload, detailOriginalFirstSelectableWordIndex((versePayload && versePayload.words) || []));
        detailOriginalSyncSelection($verse, detailOriginalFirstSelectableWordIndex((versePayload && versePayload.words) || []));
      });
    }

    function fetchDetailOriginalText(details, onDone) {
      var cacheKey = detailOriginalCacheKey(details);
      if (detailOriginalTextCache[cacheKey]) {
        onDone(detailOriginalTextCache[cacheKey]);
        return;
      }

      var originalTextUrl = getOriginalTextUrl();
      if (!originalTextUrl) {
        onDone({ verses: {} });
        return;
      }

      var merged = { verses: {} };
      var chunks = detailOriginalChunks(details);

      function fetchChunk(index) {
        if (index >= chunks.length) {
          detailOriginalTextCache[cacheKey] = merged;
          onDone(merged);
          return;
        }

        var chunk = chunks[index];
        $.ajax({
          type: 'POST',
          url: originalTextUrl,
          timeout: 20000,
          dataType: 'json',
          data: {
            csrfmiddlewaretoken: getCsrfToken(),
            book: chunk.book,
            chapter: chunk.chapter,
            start_verse: chunk.startVerse,
            end_verse: chunk.endVerse
          },
          success: function(payload) {
            $.extend(merged.verses, (payload && payload.verses) || {});
            fetchChunk(index + 1);
          },
          error: function() {
            fetchChunk(index + 1);
          }
        });
      }

      fetchChunk(0);
    }

    $(document).on('click', '.scriptura-commentary-btn', function() {
      var $btn = $(this);
      var book = $btn.data('scriptura-book');
      var chapter = $btn.data('scriptura-chapter');
      var verse = $btn.data('scriptura-verse');
      var $panel = resolveCommentaryPanel($btn, '.scriptura-commentary-panel');
      if (!$panel.length) {
        return;
      }
      if (availableScripturaCommentatorsForBook(book).length === 0) {
        $btn.hide();
        $panel.hide();
        return;
      }
      var preferredCommentatorId = getDefaultScripturaCommentatorId(book);
      if (!preferredCommentatorId) {
        $panel.html('<p class="sefaria-no-result"><em>' + uiMessage('no_scriptura_commentators_enabled') + '</em></p>').slideDown(200);
        return;
      }

      if ($panel.is(':visible')) {
        setCommentaryButtonActive($btn, false);
        $panel.slideUp(200);
        return;
      }

      setCommentaryButtonActive($btn, true);
      $panel.html(buildScripturaSourceButtons(preferredCommentatorId, book) + '<div class="scriptura-commentary-source-content">' + commentarySpinnerHtml('api', uiMessage('loading_commentary')) + '</div>').slideDown(200);
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
      var $panel = resolveCommentaryPanel($btn, '.sefaria-commentary-panel');
      if (!$panel.length) {
        return;
      }
      var cachedRelatedHtml = getCommentaryCachedValue(sefariaRelatedCache, 'sefaria_related', ref);

      if ($panel.is(':visible')) {
        setCommentaryButtonActive($btn, false);
        $panel.slideUp(200);
        return;
      }

      setCommentaryButtonActive($btn, true);
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

    $(document).on('click', '.detail-original-text-btn', function() {
      var $btn = $(this);
      var details = extractBibleStudyDetails($btn.closest('li, .our-services-text'));
      var $panel = $btn.closest('li').find('.detail-inline-original-panel').first();
      if (!$panel.length) {
        $panel = $btn.closest('.our-services-text').find('.detail-inline-original-panel').first();
      }
      if (!$panel.length || !details.book) {
        return;
      }

      if ($panel.hasClass('is-open')) {
        setCommentaryButtonActive($btn, false);
        $panel.removeClass('is-open').slideUp(200);
        return;
      }

      setCommentaryButtonActive($btn, true);
      $panel.addClass('is-open').html(commentarySpinnerHtml('api', uiMessage('loading_commentary'))).slideDown(200);
      fetchDetailOriginalText(details, function(payload) {
        if (!payload || !payload.verses || Object.keys(payload.verses).length === 0) {
          $panel.html('<p class="mb-0"><em>' + uiMessage('could_not_load_verse_text') + '</em></p>');
          return;
        }
        detailOriginalApplyPayload($panel, details, payload);
      });
    });

    $(document).on('mouseenter focus', '.detail-inline-original-word-btn', function() {
      var $btn = $(this);
      var wordIndex = Number($btn.data('wordIndex'));
      detailOriginalSyncHover($btn.closest('.detail-inline-original-verse'), wordIndex, true);
    });

    $(document).on('mouseleave blur', '.detail-inline-original-word-btn', function() {
      var $btn = $(this);
      var wordIndex = Number($btn.data('wordIndex'));
      detailOriginalSyncHover($btn.closest('.detail-inline-original-verse'), wordIndex, false);
    });

    $(document).on('click', '.detail-inline-original-word-btn', function() {
      var $btn = $(this);
      var wordIndex = Number($btn.data('wordIndex'));
      var $verse = $btn.closest('.detail-inline-original-verse');
      var versePayload = $verse.data('versePayload') || {};
      var verseDetails = $verse.data('verseDetails') || {};

      $verse.find('.detail-inline-original-word-btn').removeClass('active');
      $btn.addClass('active');
      detailOriginalSyncSelection($verse, wordIndex);
      detailOriginalRenderWordDetail($verse, verseDetails, versePayload, wordIndex);
    });

    $(document).on('mouseenter focus', '.detail-inline-original-word-translation[data-word-index], .detail-inline-original-token[data-clickable="1"]', function() {
      var $target = $(this);
      detailOriginalSyncHover($target.closest('.detail-inline-original-verse'), Number($target.data('wordIndex')), true);
    });

    $(document).on('mouseleave blur', '.detail-inline-original-word-translation[data-word-index], .detail-inline-original-token[data-clickable="1"]', function() {
      var $target = $(this);
      detailOriginalSyncHover($target.closest('.detail-inline-original-verse'), Number($target.data('wordIndex')), false);
    });

    $(document).on('click', '.detail-inline-original-word-translation[data-word-index], .detail-inline-original-token[data-clickable="1"]', function(event) {
      event.preventDefault();
      var $target = $(this);
      var wordIndex = Number($target.data('wordIndex'));
      var $verse = $target.closest('.detail-inline-original-verse');
      var versePayload = $verse.data('versePayload') || {};
      var verseDetails = $verse.data('verseDetails') || {};

      $verse.find('.detail-inline-original-word-btn').removeClass('active');
      $verse.find('.detail-inline-original-word-btn[data-word-index="' + wordIndex + '"]').addClass('active');
      detailOriginalSyncSelection($verse, wordIndex);
      detailOriginalRenderWordDetail($verse, verseDetails, versePayload, wordIndex);
    });

    $(document).on('keydown', '.detail-inline-original-word-translation[data-word-index], .detail-inline-original-token[data-clickable="1"]', function(event) {
      if (event.key !== 'Enter' && event.key !== ' ') {
        return;
      }
      event.preventDefault();
      $(this).trigger('click');
    });

    $(document).on('click', '.detail-inline-original-translate-btn', function() {
      var $btn = $(this);
      var $panel = $btn.closest('.detail-inline-original-verse');
      var isTranslated = !!$panel.data('detailOriginalTranslated');
      var nextTranslated = !isTranslated;
      $panel.data('detailOriginalTranslated', nextTranslated);
      $btn.toggleClass('active', nextTranslated);
      $btn.find('.detail-inline-original-translate-label').text(nextTranslated ? detailOriginalUiText('showOriginal') : detailOriginalUiText('translate'));
      if (nextTranslated) {
        detailOriginalApplyTranslation($panel);
      } else {
        detailOriginalRevertTranslation($panel);
      }
    });

    // ----- Sefaria Jewish Commentary END ------ \\

    // Hide Commentary buttons when no suitable Scriptura commentator exists for the reference book.
    $('.scriptura-commentary-btn').each(function() {
      var $button = $(this);
      var scripturaBook = String($button.data('scriptura-book') || '').trim();
      if (availableScripturaCommentatorsForBook(scripturaBook).length === 0) {
        $button.hide();
        resolveCommentaryPanel($button, '.scriptura-commentary-panel').hide();
      }
    });

    enhanceDetailBibleStudyLinks();

  });