const form = document.getElementById('search-form');
const maxResultsInput = document.getElementById('max-results');
const searchButton = document.getElementById('search-button');
const resultsEl = document.getElementById('results');
const statusEl = document.getElementById('status');
const customIngredientInput = document.getElementById('custom-ingredient-input');
const addCustomIngredientButton = document.getElementById('add-custom-ingredient');
const customIngredientsListEl = document.getElementById('custom-ingredients-list');
const customDietaryInput = document.getElementById('custom-dietary-input');
const addCustomDietaryButton = document.getElementById('add-custom-dietary');
const customDietaryListEl = document.getElementById('custom-dietary-list');
const customAllergyInput = document.getElementById('custom-allergy-input');
const addCustomAllergyButton = document.getElementById('add-custom-allergy');
const customAllergiesListEl = document.getElementById('custom-allergies-list');
const excludedIngredientInput = document.getElementById('excluded-ingredient-input');
const addExcludedIngredientButton = document.getElementById('add-excluded-ingredient');
const excludedIngredientsListEl = document.getElementById('excluded-ingredients-list');

let customIngredients = [];
let customDietary = [];
let customAllergies = [];
let excludedIngredients = [];

function escapeHtml(value) {
  return value
    .replaceAll('&', '&amp;')
    .replaceAll('<', '&lt;')
    .replaceAll('>', '&gt;')
    .replaceAll('"', '&quot;')
    .replaceAll("'", '&#39;');
}

function renderEmpty(message, kind = 'empty-state') {
  resultsEl.innerHTML = `<div class="${kind}">${escapeHtml(message)}</div>`;
}

function renderCustomIngredientTags() {
  if (!customIngredients.length) {
    customIngredientsListEl.innerHTML = '';
    return;
  }

  customIngredientsListEl.innerHTML = customIngredients
    .map((ingredient, index) => (
      `<button type="button" class="tag-chip" data-key="ingredient" data-index="${index}" aria-label="Remove ${escapeHtml(ingredient)}">${escapeHtml(ingredient)} ×</button>`
    ))
    .join('');
}

function createAddItemHandler(inputEl, listGetter, listSetter, renderFn) {
  return function addItem() {
    const value = inputEl.value.trim();
    if (!value) {
      return;
    }

    const list = listGetter();
    const normalized = value.toLowerCase();
    if (!list.some(item => item.toLowerCase() === normalized)) {
      listSetter([...list, value]);
      renderFn();
    }

    inputEl.value = '';
    inputEl.focus();
  };
}

function createTagRenderer(listGetter, targetEl, dataKey) {
  return function renderTags() {
    const list = listGetter();
    if (!list.length) {
      targetEl.innerHTML = '';
      return;
    }

    targetEl.innerHTML = list
      .map((item, index) => (
        `<button type="button" class="tag-chip" data-key="${dataKey}" data-index="${index}" aria-label="Remove ${escapeHtml(item)}">${escapeHtml(item)} ×</button>`
      ))
      .join('');
  };
}

const renderCustomDietaryTags = createTagRenderer(() => customDietary, customDietaryListEl, 'dietary');
const renderCustomAllergyTags = createTagRenderer(() => customAllergies, customAllergiesListEl, 'allergy');
const renderExcludedIngredientTags = createTagRenderer(() => excludedIngredients, excludedIngredientsListEl, 'excluded');

const addCustomIngredient = createAddItemHandler(
  customIngredientInput,
  () => customIngredients,
  (next) => { customIngredients = next; },
  renderCustomIngredientTags
);
const addCustomDietary = createAddItemHandler(
  customDietaryInput,
  () => customDietary,
  (next) => { customDietary = next; },
  renderCustomDietaryTags
);
const addCustomAllergy = createAddItemHandler(
  customAllergyInput,
  () => customAllergies,
  (next) => { customAllergies = next; },
  renderCustomAllergyTags
);
const addExcludedIngredient = createAddItemHandler(
  excludedIngredientInput,
  () => excludedIngredients,
  (next) => { excludedIngredients = next; },
  renderExcludedIngredientTags
);

function handleTagRemoval(event) {
  const target = event.target.closest('.tag-chip');
  if (!target) {
    return;
  }

  const key = target.dataset.key;
  const index = Number(target.dataset.index);
  if (!Number.isInteger(index) || index < 0) {
    return;
  }

  if (key === 'ingredient' && index < customIngredients.length) {
    customIngredients.splice(index, 1);
    renderCustomIngredientTags();
  } else if (key === 'dietary' && index < customDietary.length) {
    customDietary.splice(index, 1);
    renderCustomDietaryTags();
  } else if (key === 'allergy' && index < customAllergies.length) {
    customAllergies.splice(index, 1);
    renderCustomAllergyTags();
  } else if (key === 'excluded' && index < excludedIngredients.length) {
    excludedIngredients.splice(index, 1);
    renderExcludedIngredientTags();
  }
}

function addOnEnter(inputEl, addFn) {
  inputEl.addEventListener('keydown', (event) => {
    if (event.key === 'Enter') {
      event.preventDefault();
      addFn();
    }
  });
}

function renderResults(results) {
  if (!results.length) {
    renderEmpty('No results found. Try broader ingredients or fewer filters.');
    return;
  }

  function renderStars(rating) {
    if (rating === null || rating === undefined) {
      return '<span class="stars muted">No rating listed</span>';
    }

    const fullStars = Math.floor(rating);
    const hasHalfStar = rating - fullStars >= 0.5;
    const emptyStars = 5 - fullStars - (hasHalfStar ? 1 : 0);

    return `
      <span class="stars" aria-label="${rating} out of 5 stars">
        ${'★'.repeat(fullStars)}
        ${hasHalfStar ? '☆' : ''}
        ${'✩'.repeat(emptyStars)}
      </span>
    `;
  }

  resultsEl.innerHTML = results
    .map((item) => {
      const rating = renderStars(item.rating);
      const count = item.ratings_count ? `${item.ratings_count.toLocaleString()} ratings` : 'No rating count';
      const image = item.image_url
        ? `<img class="recipe-image" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.image_alt || item.title)}" loading="lazy" />`
        : `<div class="recipe-image recipe-image--placeholder">No image</div>`;

      const cookTime = item.cook_time ? `<span>${escapeHtml(item.cook_time)}</span>` : '';

      return `
        <a class="recipe-card recipe-card-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" aria-label="Open ${escapeHtml(item.title)}">
          ${image}
          <h3>${escapeHtml(item.title)}</h3>
          <div class="meta">
            <span>${rating}</span>
            <span>${escapeHtml(count)}</span>
            ${cookTime}
          </div>
        </a>
      `;
    })
    .join('');
}

async function searchRecipes(event) {
  event.preventDefault();

  const maxResults = Number(maxResultsInput.value || 10);

  // Get selected dietary restrictions
  const dietaryFilters = Array.from(
    document.querySelectorAll('input[name="vegan"]:checked, input[name="vegetarian"]:checked, input[name="halal"]:checked, input[name="kosher"]:checked')
  ).map(checkbox => checkbox.value);
  dietaryFilters.push(...customDietary);

  // Get selected allergies
  const allergyFilters = Array.from(
    document.querySelectorAll('input[name="peanuts"]:checked, input[name="tree-nuts"]:checked, input[name="milk"]:checked, input[name="eggs"]:checked, input[name="soy"]:checked, input[name="shellfish"]:checked, input[name="gluten"]:checked, input[name="dairy"]:checked')
  ).map(checkbox => checkbox.value);
  allergyFilters.push(...customAllergies);

  // Get selected common ingredients to add to base ingredients
  const commonIngredients = Array.from(
    document.querySelectorAll('.ingredient-options input[type="checkbox"]:checked')
  ).map(checkbox => checkbox.value);
  
  const combinedIngredients = [
    ...commonIngredients,
    ...customIngredients,
  ].filter(item => item);

  if (!combinedIngredients.length) {
    renderEmpty('Please enter at least one ingredient.', 'error-state');
    return;
  }

  const finalIngredients = combinedIngredients.join(', ');

  searchButton.disabled = true;
  statusEl.textContent = 'Waiting on Gemini AI...';
  resultsEl.innerHTML = '<div class="empty-state">Loading results...</div>';

  try {
    const url = new URL('/api/search/stream', window.location.origin);
    url.searchParams.set('q', finalIngredients);
    url.searchParams.set('max_results', String(maxResults));
    if (dietaryFilters.length > 0) {
      url.searchParams.set('dietary_restrictions', dietaryFilters.join(','));
    }
    if (allergyFilters.length > 0) {
      url.searchParams.set('allergies', allergyFilters.join(','));
    }
    if (excludedIngredients.length > 0) {
      url.searchParams.set('excluded_ingredients', excludedIngredients.join(','));
    }

    const response = await fetch(url);

    if (!response.ok) {
      const data = await response.json();
      if (data.code === 'GEMINI_VALIDATION_UNAVAILABLE') {
        const detailText = String(data.details || '').toLowerCase();
        if (detailText.includes('across all configured regions')) {
          throw new Error('Gemini quota is exhausted across all regions right now. Please wait a few seconds and try again.');
        }
      }

      throw new Error(data.details || data.error || 'Search failed');
    }

    if (!response.body) {
      throw new Error('Streaming is unavailable in this browser.');
    }

    const decoder = new TextDecoder();
    const reader = response.body.getReader();
    const streamedResults = [];
    let buffer = '';

    while (true) {
      const { value, done } = await reader.read();
      if (done) {
        break;
      }

      buffer += decoder.decode(value, { stream: true });
      const lines = buffer.split('\n');
      buffer = lines.pop() || '';

      for (const line of lines) {
        const payload = line.trim();
        if (!payload) {
          continue;
        }

        const message = JSON.parse(payload);
        if (message.type === 'item' && message.item) {
          streamedResults.push(message.item);
          renderResults(streamedResults);
          statusEl.textContent = `Streaming ${streamedResults.length} result${streamedResults.length === 1 ? '' : 's'}...`;
        } else if (message.type === 'error') {
          throw new Error(message.error || 'Search failed');
        }
      }
    }

    if (!streamedResults.length) {
      renderEmpty('No results found. Try broader ingredients or fewer filters.');
    }

    let statusMsg = `Found ${streamedResults.length} result${streamedResults.length === 1 ? '' : 's'} for "${finalIngredients}"`;
    const uniqueDietary = [...new Set(dietaryFilters)];
    if (uniqueDietary.length > 0) {
      statusMsg += ` matching ${uniqueDietary.join(', ')}`;
    }
    if (allergyFilters.length > 0) {
      statusMsg += ` (avoiding ${allergyFilters.join(', ')})`;
    }
    statusMsg += '.';
    statusEl.textContent = statusMsg;
  } catch (error) {
    statusEl.textContent = 'Search failed.';
    renderEmpty(error.message || 'Unable to search recipes right now.', 'error-state');
  } finally {
    searchButton.disabled = false;
  }
}

addCustomIngredientButton.addEventListener('click', addCustomIngredient);
addCustomDietaryButton.addEventListener('click', addCustomDietary);
addCustomAllergyButton.addEventListener('click', addCustomAllergy);
addExcludedIngredientButton.addEventListener('click', addExcludedIngredient);

addOnEnter(customIngredientInput, addCustomIngredient);
addOnEnter(customDietaryInput, addCustomDietary);
addOnEnter(customAllergyInput, addCustomAllergy);
addOnEnter(excludedIngredientInput, addExcludedIngredient);

customIngredientsListEl.addEventListener('click', handleTagRemoval);
customDietaryListEl.addEventListener('click', handleTagRemoval);
customAllergiesListEl.addEventListener('click', handleTagRemoval);
excludedIngredientsListEl.addEventListener('click', handleTagRemoval);

form.addEventListener('submit', searchRecipes);
renderEmpty('Add ingredients and press Search to see recipes.');


