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
const customCuisineInput = document.getElementById('custom-cuisine-input');
const addCustomCuisineButton = document.getElementById('add-custom-cuisine');
const customCuisinesListEl = document.getElementById('custom-cuisines-list');
const customEventInput = document.getElementById('custom-event-input');
const addCustomEventButton = document.getElementById('add-custom-event');
const customEventsListEl = document.getElementById('custom-events-list');
const customFoodTypeInput = document.getElementById('custom-food-type-input');
const addCustomFoodTypeButton = document.getElementById('add-custom-food-type');
const customFoodTypesListEl = document.getElementById('custom-food-types-list');
const customAllergyInput = document.getElementById('custom-allergy-input');
const addCustomAllergyButton = document.getElementById('add-custom-allergy');
const customAllergiesListEl = document.getElementById('custom-allergies-list');
const excludedIngredientInput = document.getElementById('excluded-ingredient-input');
const addExcludedIngredientButton = document.getElementById('add-excluded-ingredient');
const excludedIngredientsListEl = document.getElementById('excluded-ingredients-list');
const clearComplexityButton = document.getElementById('clear-complexity');
const selectedRecipeLabelEl = document.getElementById('selected-recipe-label');
const chatMessagesEl = document.getElementById('chat-messages');
const chatForm = document.getElementById('chat-form');
const chatInput = document.getElementById('chat-input');
const chatSendButton = document.getElementById('chat-send');
const chatClearButton = document.getElementById('chat-clear');

let customIngredients = [];
let customDietary = [];
let customCuisines = [];
let customEvents = [];
let customFoodTypes = [];
let customAllergies = [];
let excludedIngredients = [];
let latestResults = [];
let selectedRecipe = null;
let chatHistory = [];
let isChatLoading = false;

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

function renderResultsLoading(message = 'Waiting on Gemini AI...') {
  resultsEl.innerHTML = `
    <div class="empty-state loading-state">
      <span class="loading-spinner" aria-hidden="true"></span>
      <span>${escapeHtml(message)}</span>
    </div>
  `;
}

function setStatusMessage(message, loading = false) {
  if (loading) {
    statusEl.innerHTML = `<span class="loading-inline"><span class="loading-spinner" aria-hidden="true"></span><span>${escapeHtml(message)}</span></span>`;
    return;
  }
  statusEl.textContent = message;
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
const renderCustomCuisineTags = createTagRenderer(() => customCuisines, customCuisinesListEl, 'cuisine');
const renderCustomEventTags = createTagRenderer(() => customEvents, customEventsListEl, 'event');
const renderCustomFoodTypeTags = createTagRenderer(() => customFoodTypes, customFoodTypesListEl, 'food-type');
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
const addCustomCuisine = createAddItemHandler(
  customCuisineInput,
  () => customCuisines,
  (next) => { customCuisines = next; },
  renderCustomCuisineTags
);
const addCustomEvent = createAddItemHandler(
  customEventInput,
  () => customEvents,
  (next) => { customEvents = next; },
  renderCustomEventTags
);
const addCustomFoodType = createAddItemHandler(
  customFoodTypeInput,
  () => customFoodTypes,
  (next) => { customFoodTypes = next; },
  renderCustomFoodTypeTags
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
  } else if (key === 'cuisine' && index < customCuisines.length) {
    customCuisines.splice(index, 1);
    renderCustomCuisineTags();
  } else if (key === 'event' && index < customEvents.length) {
    customEvents.splice(index, 1);
    renderCustomEventTags();
  } else if (key === 'food-type' && index < customFoodTypes.length) {
    customFoodTypes.splice(index, 1);
    renderCustomFoodTypeTags();
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
  latestResults = results;

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
    .map((item, index) => {
      const rating = renderStars(item.rating);
      const count = item.ratings_count ? `${item.ratings_count.toLocaleString()} ratings` : 'No rating count';
      const image = item.image_url
        ? `<img class="recipe-image" src="${escapeHtml(item.image_url)}" alt="${escapeHtml(item.image_alt || item.title)}" loading="lazy" />`
        : `<div class="recipe-image recipe-image--placeholder">No image</div>`;

      const cookTime = item.cook_time ? `<span>${escapeHtml(item.cook_time)}</span>` : '';

      const isSelected = Boolean(selectedRecipe && selectedRecipe.url === item.url);

      return `
        <article class="recipe-card ${isSelected ? 'recipe-card--selected' : ''}">
          <div class="recipe-image-wrapper">
            ${image}
            <button type="button" class="select-recipe-button" data-select-index="${index}">${isSelected ? 'Selected' : 'Select'}</button>
          </div>
          <a class="recipe-card-link" href="${escapeHtml(item.url)}" target="_blank" rel="noreferrer" aria-label="Open ${escapeHtml(item.title)}">
            <h3>${escapeHtml(item.title)}</h3>
            <div class="meta">
              <span>${rating}</span>
              <span>${escapeHtml(count)}</span>
              ${cookTime}
            </div>
          </a>
        </article>
      `;
    })
    .join('');
}

function renderChatMessages() {
  if (!chatHistory.length) {
    chatMessagesEl.innerHTML = isChatLoading
      ? '<div class="chat-bubble chat-bubble--assistant chat-bubble--loading"><span class="loading-inline"><span class="loading-spinner" aria-hidden="true"></span><span>Ramsay is typing...</span></span></div>'
      : '<div class="chat-empty">Select one recipe card, then ask Ramsay about it.</div>';
    return;
  }

  const historyHtml = chatHistory
    .map((entry) => `
      <div class="chat-bubble chat-bubble--${entry.role}">
        <strong>${entry.role === 'assistant' ? 'Ramsay' : 'You'}:</strong>
        <span>${escapeHtml(entry.content)}</span>
      </div>
    `)
    .join('');

  const loadingHtml = isChatLoading
    ? '<div class="chat-bubble chat-bubble--assistant chat-bubble--loading"><span class="loading-inline"><span class="loading-spinner" aria-hidden="true"></span><span>Ramsay is typing...</span></span></div>'
    : '';

  chatMessagesEl.innerHTML = `${historyHtml}${loadingHtml}`;
  chatMessagesEl.scrollTop = chatMessagesEl.scrollHeight;
}

function resetChatForSelection() {
  chatHistory = [];
  renderChatMessages();
}

async function selectRecipeAtIndex(index) {
  if (!Number.isInteger(index) || index < 0 || index >= latestResults.length) {
    return;
  }

  const recipe = latestResults[index];
  selectedRecipe = {
    title: recipe.title,
    url: recipe.url,
    cook_time: recipe.cook_time || '',
    ingredients: recipe.ingredients || '',
    directions: recipe.directions || '',
  };

  selectedRecipeLabelEl.textContent = `Selected: ${recipe.title}`;
  renderResults(latestResults);
  resetChatForSelection();

  try {
    const detailsUrl = new URL('/api/recipe/context', window.location.origin);
    detailsUrl.searchParams.set('url', recipe.url);
    const response = await fetch(detailsUrl);
    if (!response.ok) {
      throw new Error('Unable to load recipe details.');
    }
    const data = await response.json();
    selectedRecipe.ingredients = data.ingredients || selectedRecipe.ingredients || '';
    selectedRecipe.directions = data.directions || selectedRecipe.directions || '';
    selectedRecipe.cook_time = data.cook_time || selectedRecipe.cook_time || '';
  } catch (error) {
    chatHistory.push({ role: 'assistant', content: error.message || 'Could not fetch recipe details yet, Chef.' });
    renderChatMessages();
  }
}

async function sendChatMessage(event) {
  event.preventDefault();

  const message = chatInput.value.trim();
  if (!message) {
    return;
  }

  if (!selectedRecipe) {
    chatHistory.push({ role: 'assistant', content: 'Select one recipe first, Chef.' });
    renderChatMessages();
    return;
  }

  chatHistory.push({ role: 'user', content: message });
  renderChatMessages();
  chatInput.value = '';
  chatSendButton.disabled = true;
  isChatLoading = true;
  renderChatMessages();

  try {
    const response = await fetch('/api/chat/recipe', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({
        message,
        recipe: selectedRecipe,
        history: chatHistory,
      }),
    });

    const data = await response.json();
    if (!response.ok) {
      throw new Error(data.error || data.details || 'Chat failed.');
    }

    isChatLoading = false;
    chatHistory.push({ role: 'assistant', content: data.reply || 'Spot on, Chef.' });
    renderChatMessages();
  } catch (error) {
    isChatLoading = false;
    chatHistory.push({ role: 'assistant', content: error.message || 'Kitchen comms are down, Chef.' });
    renderChatMessages();
  } finally {
    if (isChatLoading) {
      isChatLoading = false;
      renderChatMessages();
    }
    chatSendButton.disabled = false;
  }
}

async function searchRecipes(event) {
  event.preventDefault();

  const maxResults = Number(maxResultsInput.value || 10);
  const selectedComplexityEl = document.querySelector('input[name="recipe-complexity"]:checked');
  const selectedComplexity = selectedComplexityEl ? selectedComplexityEl.value : '';

  // Get selected dietary restrictions
  const dietaryFilters = Array.from(
    document.querySelectorAll('input[name="vegan"]:checked, input[name="vegetarian"]:checked, input[name="halal"]:checked, input[name="kosher"]:checked')
  ).map(checkbox => checkbox.value);
  dietaryFilters.push(...customDietary);

  // Get selected cuisines
  const cuisineFilters = Array.from(
    document.querySelectorAll('input[name^="cuisine-"]:checked')
  ).map((checkbox) => checkbox.value);
  cuisineFilters.push(...customCuisines);

  // Get selected events
  const eventFilters = Array.from(
    document.querySelectorAll('input[name^="event-"]:checked')
  ).map((checkbox) => checkbox.value);
  eventFilters.push(...customEvents);

  // Get selected food types
  const foodTypeFilters = Array.from(
    document.querySelectorAll('input[name^="food-type-"]:checked')
  ).map((checkbox) => checkbox.value);
  foodTypeFilters.push(...customFoodTypes);

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
  setStatusMessage('Waiting on Gemini AI...', true);
  renderResultsLoading('Loading results...');
  selectedRecipe = null;
  selectedRecipeLabelEl.textContent = 'No recipe selected.';
  resetChatForSelection();

  try {
    const url = new URL('/api/search/stream', window.location.origin);
    url.searchParams.set('q', finalIngredients);
    url.searchParams.set('max_results', String(maxResults));
    if (dietaryFilters.length > 0) {
      url.searchParams.set('dietary_restrictions', dietaryFilters.join(','));
    }
    if (cuisineFilters.length > 0) {
      url.searchParams.set('cuisines', cuisineFilters.join(','));
    }
    if (eventFilters.length > 0) {
      url.searchParams.set('events', eventFilters.join(','));
    }
    if (foodTypeFilters.length > 0) {
      url.searchParams.set('food_types', foodTypeFilters.join(','));
    }
    if (allergyFilters.length > 0) {
      url.searchParams.set('allergies', allergyFilters.join(','));
    }
    if (excludedIngredients.length > 0) {
      url.searchParams.set('excluded_ingredients', excludedIngredients.join(','));
    }
    if (selectedComplexity) {
      url.searchParams.set('complexity', selectedComplexity);
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
          setStatusMessage(`Streaming ${streamedResults.length} result${streamedResults.length === 1 ? '' : 's'}...`, true);
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
    if (cuisineFilters.length > 0) {
      statusMsg += ` [cuisine: ${cuisineFilters.join(', ')}]`;
    }
    if (eventFilters.length > 0) {
      statusMsg += ` [event: ${eventFilters.join(', ')}]`;
    }
    if (foodTypeFilters.length > 0) {
      statusMsg += ` [food type: ${foodTypeFilters.join(', ')}]`;
    }
    if (selectedComplexity) {
      statusMsg += ` [${selectedComplexity}]`;
    }
    statusMsg += '.';
    setStatusMessage(statusMsg);
  } catch (error) {
    setStatusMessage('Search failed.');
    renderEmpty(error.message || 'Unable to search recipes right now.', 'error-state');
  } finally {
    searchButton.disabled = false;
  }
}

addCustomIngredientButton.addEventListener('click', addCustomIngredient);
addCustomDietaryButton.addEventListener('click', addCustomDietary);
addCustomCuisineButton.addEventListener('click', addCustomCuisine);
addCustomEventButton.addEventListener('click', addCustomEvent);
addCustomFoodTypeButton.addEventListener('click', addCustomFoodType);
addCustomAllergyButton.addEventListener('click', addCustomAllergy);
addExcludedIngredientButton.addEventListener('click', addExcludedIngredient);

resultsEl.addEventListener('click', (event) => {
  const button = event.target.closest('.select-recipe-button');
  if (!button) {
    return;
  }
  const index = Number(button.dataset.selectIndex);
  selectRecipeAtIndex(index);
});

addOnEnter(customIngredientInput, addCustomIngredient);
addOnEnter(customDietaryInput, addCustomDietary);
addOnEnter(customCuisineInput, addCustomCuisine);
addOnEnter(customEventInput, addCustomEvent);
addOnEnter(customFoodTypeInput, addCustomFoodType);
addOnEnter(customAllergyInput, addCustomAllergy);
addOnEnter(excludedIngredientInput, addExcludedIngredient);

customIngredientsListEl.addEventListener('click', handleTagRemoval);
customDietaryListEl.addEventListener('click', handleTagRemoval);
customCuisinesListEl.addEventListener('click', handleTagRemoval);
customEventsListEl.addEventListener('click', handleTagRemoval);
customFoodTypesListEl.addEventListener('click', handleTagRemoval);
customAllergiesListEl.addEventListener('click', handleTagRemoval);
excludedIngredientsListEl.addEventListener('click', handleTagRemoval);

clearComplexityButton.addEventListener('click', () => {
  document.querySelectorAll('input[name="recipe-complexity"]').forEach((input) => {
    input.checked = false;
  });
});

chatForm.addEventListener('submit', sendChatMessage);
chatClearButton.addEventListener('click', () => {
  chatHistory = [];
  renderChatMessages();
});

form.addEventListener('submit', searchRecipes);
renderEmpty('Add ingredients and press Search to see recipes.');
renderChatMessages();


