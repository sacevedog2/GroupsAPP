const STORAGE_KEYS = {
  session: "groupsapp_session_v4",
  settings: "groupsapp_settings_v5",
  ui: "groupsapp_ui_v4",
};

const DEFAULT_SETTINGS = {
  auth: "/api/auth",
  messaging: "/api/messaging",
  groups: "/api/groups",
  notifications: "/api/notifications",
};

const POLL_MS = 4000;
const NOTIFICATION_WIDGET_MS = 3000;

const state = {
  authMode: "login",
  token: "",
  user: null,
  settings: { ...DEFAULT_SETTINGS },
  directConversations: [],
  groupConversations: [],
  conversations: [],
  selectedConversationKey: "",
  messagesByConversation: {},
  usersById: {},
  groupMembersByGroup: {},
  groupChannelsByGroup: {},
  notifications: [],
  unreadNotificationCount: 0,
  notificationSeenIds: {},
  notificationToastTimers: {},
  notificationsInitialized: false,
  groupDetailsOpen: false,
  pollTimer: null,
};

const refs = {};

function $(id) {
  return document.getElementById(id);
}

function cacheRefs() {
  const ids = [
    "authView",
    "appView",
    "btnTabLogin",
    "btnTabRegister",
    "loginForm",
    "registerForm",
    "loginEmail",
    "loginPassword",
    "registerEmail",
    "registerPassword",
    "btnLogin",
    "btnRegister",
    "btnLogout",
    "btnRefreshInbox",
    "btnOpenSettings",
    "btnCloseSettings",
    "btnSaveSettings",
    "btnClearOutput",
    "btnStartConversation",
    "btnCreateGroup",
    "btnSendMessage",
    "btnAcceptDirect",
    "btnGroupDetails",
    "identityHeadline",
    "recipientUserId",
    "conversationList",
    "inboxCount",
    "chatTitle",
    "chatSubtitle",
    "chatPresence",
    "groupDetailsPanel",
    "groupDetailsDescription",
    "groupDetailsId",
    "groupDetailsChannels",
    "groupDetailsMembers",
    "groupDetailsCount",
    "groupAdminPanel",
    "groupEditForm",
    "groupEditName",
    "groupEditDescription",
    "btnUpdateGroup",
    "groupAddMemberForm",
    "groupAddMemberInput",
    "btnAddGroupMember",
    "groupCreateChannelForm",
    "groupChannelName",
    "groupChannelMembers",
    "btnCreateChannel",
    "btnDeleteGroup",
    "messages",
    "composerForm",
    "messageInput",
    "messageFiles",
    "selectedFiles",
    "startConversationForm",
    "createGroupForm",
    "groupName",
    "groupDescription",
    "groupMembersInput",
    "settingsDrawer",
    "drawerBackdrop",
    "authBaseUrl",
    "messagingBaseUrl",
    "groupsBaseUrl",
    "notificationsBaseUrl",
    "output",
    "toastRegion",
    "notificationWidget",
    "notificationCount",
    "notificationList",
  ];

  for (const id of ids) {
    refs[id] = $(id);
  }
}

function readStorage(key, fallback) {
  try {
    const raw = localStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) {
    return fallback;
  }
}

function writeStorage(key, value) {
  localStorage.setItem(key, JSON.stringify(value));
}

function readSessionStorage(key, fallback) {
  try {
    const raw = sessionStorage.getItem(key);
    return raw ? JSON.parse(raw) : fallback;
  } catch (_) {
    return fallback;
  }
}

function writeSessionStorage(key, value) {
  sessionStorage.setItem(key, JSON.stringify(value));
}

function loadPersistedState() {
  const session = readSessionStorage(STORAGE_KEYS.session, {});
  const settings = readStorage(STORAGE_KEYS.settings, DEFAULT_SETTINGS);
  const ui = readStorage(STORAGE_KEYS.ui, {});

  localStorage.removeItem(STORAGE_KEYS.session);
  state.token = session.token || "";
  state.user = session.user || null;
  state.settings = { ...DEFAULT_SETTINGS, ...settings };
  state.authMode = ui.authMode === "register" ? "register" : "login";
  state.selectedConversationKey = ui.selectedConversationKey || "";
}

function persistSession() {
  writeSessionStorage(STORAGE_KEYS.session, {
    token: state.token,
    user: state.user,
  });
}

function persistSettings() {
  writeStorage(STORAGE_KEYS.settings, state.settings);
}

function persistUi() {
  writeStorage(STORAGE_KEYS.ui, {
    authMode: state.authMode,
    selectedConversationKey: state.selectedConversationKey,
  });
}

function normalizeBaseUrl(value, fallback) {
  const trimmed = value.trim();
  return (trimmed || fallback).replace(/\/+$/, "");
}

function escapeHtml(value) {
  return String(value)
    .replaceAll("&", "&amp;")
    .replaceAll("<", "&lt;")
    .replaceAll(">", "&gt;")
    .replaceAll('"', "&quot;")
    .replaceAll("'", "&#39;");
}

function formatDate(value) {
  if (!value) return "";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return "";
  return new Intl.DateTimeFormat(navigator.language || undefined, {
    dateStyle: "short",
    timeStyle: "short",
    timeZone: Intl.DateTimeFormat().resolvedOptions().timeZone,
  }).format(date);
}

function formatBytes(bytes) {
  const value = Number(bytes) || 0;
  if (value < 1024) return `${value} B`;
  const units = ["KB", "MB", "GB"];
  let size = value / 1024;
  let unit = units[0];
  for (let index = 1; index < units.length && size >= 1024; index += 1) {
    size /= 1024;
    unit = units[index];
  }
  return `${size.toFixed(size >= 10 ? 0 : 1)} ${unit}`;
}

function notificationIdValue(notificationId) {
  return String(notificationId ?? "");
}

function parseCommaList(value) {
  const unique = [];
  for (const piece of value.split(",")) {
    const normalized = piece.trim().toLowerCase();
    if (normalized && !unique.includes(normalized)) {
      unique.push(normalized);
    }
  }
  return unique;
}

function getSelectedFiles() {
  return Array.from(refs.messageFiles?.files || []);
}

function attachmentContentUrl(attachmentId) {
  return `${state.settings.messaging}/v1/attachments/${encodeURIComponent(
    attachmentId
  )}/content`;
}

function isImageAttachment(attachment) {
  const contentType = String(attachment.content_type || "").toLowerCase();
  if (contentType.startsWith("image/")) return true;

  const filename = String(attachment.original_filename || "").toLowerCase();
  return /\.(apng|avif|gif|jpe?g|png|svg|webp)$/.test(filename);
}

function renderAttachment(attachment) {
  const url = attachmentContentUrl(attachment.id);
  const filename = attachment.original_filename;
  if (isImageAttachment(attachment)) {
    return `
      <a class="image-attachment" href="${escapeHtml(url)}" target="_blank" rel="noopener">
        <img src="${escapeHtml(url)}" alt="${escapeHtml(filename)}" loading="lazy" />
      </a>
    `;
  }

  return `
    <a class="attachment-link" href="${escapeHtml(url)}" download="${escapeHtml(
      filename
    )}" target="_blank" rel="noopener">
      <span>${escapeHtml(filename)}</span>
      <small>${escapeHtml(formatBytes(attachment.size_bytes))}</small>
    </a>
  `;
}

function getAttachmentPreviewLabel(message) {
  const attachments = Array.isArray(message?.attachments) ? message.attachments : [];
  if (!attachments.length) return "";
  return attachments.some((attachment) => isImageAttachment(attachment))
    ? "Imagen"
    : "Archivo adjunto";
}

function renderSelectedFiles() {
  const files = getSelectedFiles();
  if (!files.length) {
    refs.selectedFiles.innerHTML = "";
    refs.selectedFiles.classList.add("hidden");
    return;
  }

  refs.selectedFiles.classList.remove("hidden");
  refs.selectedFiles.innerHTML = files
    .map(
      (file) => `
        <span class="selected-file" title="${escapeHtml(file.name)}">
          ${escapeHtml(file.name)}
          <small>${escapeHtml(formatBytes(file.size))}</small>
        </span>
      `
    )
    .join("");
}

function showToast(message, tone = "info") {
  const toast = document.createElement("article");
  toast.className = `toast ${tone}`;
  toast.textContent = message;
  refs.toastRegion.appendChild(toast);
  window.setTimeout(() => toast.remove(), 3200);
}

function setOutput(payload) {
  refs.output.textContent =
    typeof payload === "string" ? payload : JSON.stringify(payload, null, 2);
}

function conversationKey(scopeType, scopeId) {
  return `${scopeType}:${scopeId}`;
}

function setAuthMode(mode) {
  state.authMode = mode === "register" ? "register" : "login";
  persistUi();
  refs.btnTabLogin.classList.toggle("active", state.authMode === "login");
  refs.btnTabRegister.classList.toggle("active", state.authMode === "register");
  refs.loginForm.classList.toggle("hidden", state.authMode !== "login");
  refs.registerForm.classList.toggle("hidden", state.authMode !== "register");
}

function isAuthenticated() {
  return Boolean(state.token && state.user?.user_id);
}

function updateShell() {
  const loggedIn = isAuthenticated();
  refs.authView.classList.toggle("hidden", loggedIn);
  refs.appView.classList.toggle("hidden", !loggedIn);
}

function syncSettingsInputs() {
  refs.authBaseUrl.value = state.settings.auth;
  refs.messagingBaseUrl.value = state.settings.messaging;
  refs.groupsBaseUrl.value = state.settings.groups;
  refs.notificationsBaseUrl.value = state.settings.notifications;
}

function openSettingsDrawer(open) {
  refs.settingsDrawer.classList.toggle("hidden", !open);
  refs.drawerBackdrop.classList.toggle("hidden", !open);
}

function getSelectedConversation() {
  return (
    state.conversations.find(
      (conversation) => conversation.key === state.selectedConversationKey
    ) || null
  );
}

function updateProfileHeader() {
  const user = state.user;
  if (!user) return;
  refs.identityHeadline.textContent = `Bienvenido @${user.user_id}`;
}

function rebuildConversations() {
  const byActivity = (left, right) => {
    const leftUnread = left.unread_count > 0 ? 1 : 0;
    const rightUnread = right.unread_count > 0 ? 1 : 0;
    if (leftUnread !== rightUnread) return rightUnread - leftUnread;
    const leftTime = Date.parse(left.updated_at || "") || 0;
    const rightTime = Date.parse(right.updated_at || "") || 0;
    return rightTime - leftTime;
  };
  const sortedDirect = [...state.directConversations].sort(byActivity);
  const sortedGroups = [...state.groupConversations].sort((left, right) => {
    return byActivity(left, right);
  });
  const groupedConversations = [];
  for (const group of sortedGroups) {
    groupedConversations.push(group);
    const isExpanded =
      state.selectedConversationKey === group.key ||
      group.channels?.some((channel) => channel.key === state.selectedConversationKey);
    if (isExpanded) {
      groupedConversations.push(...(group.channels || []));
    }
  }

  state.conversations = [...sortedDirect, ...groupedConversations];
}

function getConversationLabel(conversation) {
  if (conversation.scope_type === "direct") {
    const profile = state.usersById[conversation.peer_user_id];
    return profile?.display_name || conversation.peer_user_id;
  }
  if (conversation.scope_type === "channel") {
    return `#${conversation.title}`;
  }
  return conversation.title;
}

function renderConversationList() {
  refs.inboxCount.textContent = String(state.conversations.length);

  if (!state.conversations.length) {
    refs.conversationList.innerHTML =
      '<li class="conversation-empty">Tu bandeja está vacía. Puedes abrir un chat directo o crear un grupo.</li>';
    return;
  }

  refs.conversationList.innerHTML = state.conversations
    .map((conversation) => {
      const active = conversation.key === state.selectedConversationKey ? "active" : "";
      const itemClass = conversation.scope_type === "channel" ? "conversation-channel" : "";
      const label = getConversationLabel(conversation);
      const subtitle =
        conversation.scope_type === "direct"
          ? `@${conversation.peer_user_id}`
          : conversation.scope_type === "channel"
            ? conversation.group_title || "Canal del grupo"
          : "";
      const preview = conversation.preview || "Todavía no hay mensajes.";
      const pending = conversation.request_status === "pending";
      const pendingLabel =
        pending && conversation.requester_user_id === state.user.user_id
          ? "esperando aceptación"
          : pending
            ? "solicitud pendiente"
            : "";
      const unreadIcon =
        conversation.unread_count > 0 ? '<span class="unread-dot" title="No leído"></span>' : "";
      const unread =
        pending
          ? `<span class="kind-badge">${pendingLabel}</span>`
          : conversation.unread_count > 0
          ? `<span class="unread-badge">${unreadIcon}${conversation.unread_count}</span>`
          : `<span class="kind-badge">${
              conversation.scope_type === "group"
                ? "grupo"
                : conversation.scope_type === "channel"
                  ? "canal"
                  : "directo"
            }</span>`;
      const presence =
        conversation.scope_type === "direct"
          ? pending
            ? '<span class="presence-pill pending">pendiente</span>'
            : `<span class="presence-pill ${
                state.usersById[conversation.peer_user_id]?.is_online ? "online" : "offline"
              }">${
                state.usersById[conversation.peer_user_id]?.is_online ? "online" : "offline"
              }</span>`
          : `<span class="presence-pill offline">${escapeHtml(
              conversation.scope_type === "channel"
                ? conversation.member_count
                  ? `${conversation.member_count} miembros`
                  : "canal"
                : conversation.member_count
                  ? `${conversation.member_count} miembros`
                  : "grupo"
            )}</span>`;

      return `
        <li>
          <article class="conversation-item ${itemClass} ${active}" data-conversation-key="${escapeHtml(
            conversation.key
          )}">
            <div class="conversation-top">
              <div>
                <strong>${escapeHtml(label)}</strong>
                ${subtitle ? `<small>${escapeHtml(subtitle)}</small>` : ""}
              </div>
              ${unread}
            </div>
            <p>${escapeHtml(preview)}</p>
            <div class="conversation-bottom">
              <time>${escapeHtml(formatDate(conversation.updated_at))}</time>
              ${presence}
            </div>
          </article>
        </li>
      `;
    })
    .join("");

  for (const item of refs.conversationList.querySelectorAll("[data-conversation-key]")) {
    item.addEventListener("click", () => {
      const key = item.getAttribute("data-conversation-key");
      if (key) {
        selectConversation(key);
      }
    });
  }
}

function renderChatHeader() {
  const conversation = getSelectedConversation();
  if (!conversation) {
    refs.chatTitle.textContent = "Selecciona una conversación";
    refs.chatSubtitle.textContent =
      "Cuando abras un chat, los mensajes aparecerán aquí.";
    refs.chatPresence.classList.add("hidden");
    refs.btnAcceptDirect.classList.add("hidden");
    refs.btnGroupDetails.classList.add("hidden");
    return;
  }

  if (conversation.scope_type === "direct") {
    const profile = state.usersById[conversation.peer_user_id];
    const pending = conversation.request_status === "pending";
    const outgoingPending = pending && conversation.requester_user_id === state.user.user_id;
    refs.chatTitle.textContent = profile?.display_name || conversation.peer_user_id;
    refs.chatSubtitle.textContent = outgoingPending
      ? `@${conversation.peer_user_id} todavía no ha aceptado tu solicitud.`
      : pending
        ? `@${conversation.peer_user_id} quiere iniciar un chat contigo.`
        : `@${conversation.peer_user_id}`;
    refs.chatPresence.textContent = pending
      ? "pendiente"
      : profile?.is_online
        ? "online"
        : "offline";
    refs.chatPresence.classList.remove("hidden");
    refs.chatPresence.classList.toggle("pending", pending);
    refs.chatPresence.classList.toggle("online", !pending && Boolean(profile?.is_online));
    refs.chatPresence.classList.toggle("offline", !pending && !profile?.is_online);
    refs.btnAcceptDirect.classList.toggle("hidden", !pending || outgoingPending);
    refs.btnGroupDetails.classList.add("hidden");
    return;
  }

  if (conversation.scope_type === "channel") {
    refs.chatTitle.textContent = `#${conversation.title}`;
    refs.chatSubtitle.textContent = conversation.group_title
      ? `Canal de ${conversation.group_title}`
      : "Canal del grupo";
    refs.chatPresence.textContent = "canal";
    refs.chatPresence.classList.remove("hidden");
    refs.chatPresence.classList.remove("pending");
    refs.chatPresence.classList.remove("online");
    refs.chatPresence.classList.add("offline");
    refs.btnAcceptDirect.classList.add("hidden");
    refs.btnGroupDetails.classList.add("hidden");
    return;
  }

  refs.chatTitle.textContent = conversation.title;
  refs.chatSubtitle.textContent = conversation.subtitle || "Grupo";
  refs.chatPresence.textContent = "grupo";
  refs.chatPresence.classList.remove("hidden");
  refs.chatPresence.classList.remove("pending");
  refs.chatPresence.classList.remove("online");
  refs.chatPresence.classList.add("offline");
  refs.btnAcceptDirect.classList.add("hidden");
  refs.btnGroupDetails.classList.remove("hidden");
  refs.btnGroupDetails.textContent = state.groupDetailsOpen ? "Ocultar detalles" : "Detalles";
}

function getPeerReceiptStatus(message) {
  if (!Array.isArray(message.receipts)) return "";
  const peerReceipt = message.receipts.find((receipt) => receipt.user_id !== state.user.user_id);
  return peerReceipt?.status || "";
}

function getGroupReceiptStatusLabel(message) {
  const receipts = Array.isArray(message.receipts)
    ? message.receipts.filter((receipt) => receipt.user_id !== state.user.user_id)
    : [];

  if (!receipts.length) return receiptStatusLabel("sent");

  let readCount = 0;
  let deliveredCount = 0;
  for (const receipt of receipts) {
    if (receipt.status === "read") {
      readCount += 1;
      continue;
    }
    if (receipt.status === "delivered") {
      deliveredCount += 1;
    }
  }

  if (readCount === receipts.length) {
    return `leído por ${readCount}`;
  }

  const reachedCount = readCount + deliveredCount;
  if (reachedCount > 0) {
    return `entregado a ${reachedCount} de ${receipts.length}`;
  }

  return receiptStatusLabel("sent");
}

function receiptStatusLabel(status) {
  const labels = {
    sent: "enviado",
    delivered: "entregado",
    read: "leído",
  };
  return labels[status] || status;
}

function getUnreadNotificationsForScope(scopeType, scopeId) {
  return state.notifications.filter(
    (notification) =>
      !notification.is_read &&
      notification.scope_type === scopeType &&
      notification.scope_id === scopeId
  );
}

function dismissNotificationWidget() {
  refs.notificationWidget.classList.add("hidden");
  refs.notificationWidget.classList.remove("notification-widget-live");
}

function clearNotificationToasts() {
  for (const timerId of Object.values(state.notificationToastTimers)) {
    window.clearTimeout(timerId);
  }
  state.notificationToastTimers = {};
  refs.notificationList.innerHTML = "";
  dismissNotificationWidget();
}

function removeNotificationToast(notificationId) {
  const normalizedId = notificationIdValue(notificationId);
  const item = [...refs.notificationList.children].find(
    (child) => child.dataset.notificationId === normalizedId
  );
  if (item) item.remove();
  if (state.notificationToastTimers[normalizedId]) {
    window.clearTimeout(state.notificationToastTimers[normalizedId]);
    delete state.notificationToastTimers[normalizedId];
  }
  renderNotificationWidget();
}

function getConversationForNotification(notification) {
  return (
    state.conversations.find(
      (conversation) =>
        conversation.scope_type === notification.scope_type &&
        conversation.scope_id === notification.scope_id
    ) || null
  );
}

function getNotificationContextLabel(notification) {
  const conversation = getConversationForNotification(notification);
  if (conversation) {
    const label = getConversationLabel(conversation);
    if (conversation.scope_type === "group") return `Grupo: ${label}`;
    if (conversation.scope_type === "channel") return `Canal: ${label}`;
    return `Chat: ${label}`;
  }
  if (notification.scope_type === "group") return "Grupo";
  if (notification.scope_type === "channel") return "Canal";
  if (notification.scope_type === "direct") return "Chat directo";
  return "Conversación";
}

function enqueueNotificationToast(notification) {
  const normalizedId = notificationIdValue(notification.id);
  if (state.notificationToastTimers[normalizedId]) return;

  const item = document.createElement("article");
  item.className = "notification-item";
  item.dataset.notificationId = normalizedId;
  item.innerHTML = `
    <strong>${escapeHtml(notification.title)}</strong>
    <small>${escapeHtml(getNotificationContextLabel(notification))}</small>
    <p>${escapeHtml(notification.body)}</p>
    <time>${escapeHtml(formatDate(notification.created_at))}</time>
  `;

  refs.notificationList.prepend(item);
  state.notificationToastTimers[normalizedId] = window.setTimeout(() => {
    removeNotificationToast(normalizedId);
  }, NOTIFICATION_WIDGET_MS);

  refs.notificationWidget.classList.remove("hidden");
  refs.notificationWidget.classList.remove("notification-widget-live");
  void refs.notificationWidget.offsetWidth;
  refs.notificationWidget.classList.add("notification-widget-live");
  renderNotificationWidget();
}

function renderNotificationWidget() {
  refs.notificationCount.textContent = String(state.unreadNotificationCount);
  const shouldShow = isAuthenticated() && refs.notificationList.childElementCount > 0;
  refs.notificationWidget.classList.toggle("hidden", !shouldShow);
  if (!shouldShow) {
    refs.notificationWidget.classList.remove("notification-widget-live");
  }
}

function renderMessages() {
  const conversation = getSelectedConversation();
  if (!conversation) {
    refs.messages.innerHTML =
      '<div class="message-empty">Selecciona una conversación para empezar a hablar.</div>';
    return;
  }

  const messages = state.messagesByConversation[conversation.key] || [];
  if (!messages.length) {
    refs.messages.innerHTML =
      '<div class="message-empty">Todavía no hay mensajes en esta conversación.</div>';
    return;
  }

  refs.messages.innerHTML = messages
    .map((message) => {
      const mine = message.sender_id === state.user.user_id;
      const status = mine
        ? conversation.scope_type === "direct"
          ? `Estado: ${receiptStatusLabel(getPeerReceiptStatus(message) || "sent")}`
          : `Estado: ${getGroupReceiptStatusLabel(message)}`
        : "";
      const attachments = Array.isArray(message.attachments) ? message.attachments : [];
      const attachmentsHtml = attachments.length
        ? `
          <div class="message-attachments">
            ${attachments.map((attachment) => renderAttachment(attachment)).join("")}
          </div>
        `
        : "";
      const bodyHtml = message.body
        ? `<div class="message-body">${escapeHtml(message.body)}</div>`
        : "";

      return `
        <article class="message ${mine ? "outgoing" : "incoming"}">
          <div class="message-head">
            <strong>${escapeHtml(
              mine
                ? "Tú"
                : state.usersById[message.sender_id]?.display_name || message.sender_id
            )}</strong>
            <time>${escapeHtml(formatDate(message.created_at))}</time>
          </div>
          ${bodyHtml}
          ${attachmentsHtml}
          <div class="message-foot">
            <span>${escapeHtml(status)}</span>
          </div>
        </article>
      `;
    })
    .join("");

  refs.messages.scrollTop = refs.messages.scrollHeight;
}

function renderGroupDetails() {
  const conversation = getSelectedConversation();
  const visible = Boolean(
    state.groupDetailsOpen && conversation && conversation.scope_type === "group"
  );
  refs.groupDetailsPanel.classList.toggle("hidden", !visible);
  if (!visible) {
    refs.groupAdminPanel.classList.add("hidden");
    return;
  }

  const members = state.groupMembersByGroup[conversation.scope_id] || [];
  const currentMembership = members.find((member) => member.user_id === state.user.user_id);
  const isAdmin = currentMembership?.role === "admin";
  refs.groupDetailsDescription.textContent =
    conversation.subtitle && conversation.subtitle !== "Grupo"
      ? conversation.subtitle
      : "Este grupo no tiene descripción.";
  refs.groupDetailsId.textContent = `ID único del grupo: ${conversation.scope_id}`;
  refs.groupDetailsCount.textContent = `${members.length} ${
    members.length === 1 ? "miembro" : "miembros"
  }`;
  refs.groupAdminPanel.classList.toggle("hidden", !isAdmin);
  if (isAdmin) {
    if (document.activeElement !== refs.groupEditName) {
      refs.groupEditName.value = conversation.title || "";
    }
    if (document.activeElement !== refs.groupEditDescription) {
      refs.groupEditDescription.value =
        conversation.subtitle && conversation.subtitle !== "Grupo" ? conversation.subtitle : "";
    }
  }

  const channels = state.groupChannelsByGroup[conversation.scope_id] || [];
  refs.groupDetailsChannels.innerHTML = `
    <div class="section-subhead">
      <strong>Canales</strong>
      <span>${channels.length} ${channels.length === 1 ? "canal" : "canales"}</span>
    </div>
    ${
      channels.length
        ? channels
            .map((channel) => {
              const channelMembers = Array.isArray(channel.members) ? channel.members : [];
              const memberChips = channelMembers.length
                ? channelMembers
                    .map((member) => {
                      const profile = state.usersById[member.user_id];
                      const label = profile?.display_name || member.user_id;
                      const removeButton = isAdmin
                        ? `<button type="button" class="btn btn-ghost btn-channel-remove" data-channel-id="${escapeHtml(
                            channel.id
                          )}" data-channel-remove-user="${escapeHtml(member.user_id)}">Quitar</button>`
                        : "";
                      return `
                        <span class="channel-member-chip">
                          @${escapeHtml(label)}
                          ${removeButton}
                        </span>
                      `;
                    })
                    .join("")
                : '<span class="member-empty">Sin miembros asignados.</span>';
              const addForm = isAdmin
                ? `
                  <form class="channel-add-member-form" data-channel-add-form="${escapeHtml(
                    channel.id
                  )}">
                    <input data-channel-add-input="${escapeHtml(
                      channel.id
                    )}" placeholder="Añadir usuario al canal" />
                    <button type="submit" class="btn btn-ghost">Añadir</button>
                  </form>
                `
                : "";
              return `
                <article class="channel-row">
                  <div class="channel-row-head">
                    <strong>#${escapeHtml(channel.name)}</strong>
                    <small>${channelMembers.length} ${
                channelMembers.length === 1 ? "miembro" : "miembros"
              }</small>
                  </div>
                  <div class="channel-members">${memberChips}</div>
                  ${addForm}
                </article>
              `;
            })
            .join("")
        : '<div class="member-empty">Este grupo todavía no tiene canales.</div>'
    }
  `;

  if (!members.length) {
    refs.groupDetailsMembers.innerHTML =
      '<div class="member-empty">Cargando miembros del grupo...</div>';
    return;
  }

  refs.groupDetailsMembers.innerHTML = members
    .map((member) => {
      const isSelf = member.user_id === state.user.user_id;
      const profile = isSelf ? state.user : state.usersById[member.user_id];
      const online = Boolean(profile?.is_online);
      const name = isSelf
        ? profile?.display_name || "Tú"
        : profile?.display_name || member.user_id;
      const removeButton =
        isAdmin && !isSelf
          ? `<button type="button" class="btn btn-ghost btn-member-remove" data-remove-user="${escapeHtml(
              member.user_id
            )}">Eliminar</button>`
          : "";
      const directButton = !isSelf
        ? `<button type="button" class="btn btn-ghost btn-member-direct" data-direct-user="${escapeHtml(
            member.user_id
          )}">Chat directo</button>`
        : "";
      return `
        <article class="member-row">
          <div>
            <strong>${escapeHtml(name)}</strong>
            <small>@${escapeHtml(member.user_id)} · ${escapeHtml(member.role || "member")}</small>
          </div>
          <div class="member-actions">
            <span class="presence-pill ${online ? "online" : "offline"}">
              ${online ? "online" : "offline"}
            </span>
            ${directButton}
            ${removeButton}
          </div>
        </article>
      `;
    })
    .join("");
}

function renderApp() {
  updateShell();
  updateProfileHeader();
  rebuildConversations();
  renderConversationList();
  renderChatHeader();
  renderGroupDetails();
  renderMessages();
  renderNotificationWidget();
}

async function runWithBusyState(button, label, action) {
  const previous = button?.textContent;
  if (button) {
    button.disabled = true;
    button.textContent = label;
  }

  try {
    await action();
  } finally {
    if (button) {
      button.disabled = false;
      button.textContent = previous;
    }
  }
}

async function request(url, options = {}) {
  const headers = { ...(options.headers || {}) };
  if (state.token) {
    headers.Authorization = `Bearer ${state.token}`;
  }
  if (options.body !== undefined && !(options.body instanceof FormData)) {
    headers["Content-Type"] = "application/json";
  }

  let response;
  try {
    response = await fetch(url, { ...options, headers });
  } catch (error) {
    const message = `No se pudo conectar con ${url}`;
    setOutput({ error: message, detail: String(error) });
    throw new Error(message);
  }

  const text = await response.text();
  let body = text;
  try {
    body = text ? JSON.parse(text) : {};
  } catch (_) {
    body = text;
  }

  setOutput({
    request: { method: options.method || "GET", url },
    response: { status: response.status, statusText: response.statusText, body },
  });

  if (!response.ok) {
    const detail =
      typeof body === "string" ? body : body?.detail || JSON.stringify(body);
    throw new Error(`${response.status} ${response.statusText}: ${detail}`);
  }

  return body;
}

async function uploadAttachment(file, conversation) {
  const formData = new FormData();
  formData.append("uploader_id", state.user.user_id);
  formData.append("scope_type", conversation.scope_type);
  formData.append("scope_id", conversation.scope_id);
  formData.append("file", file);

  return request(`${state.settings.messaging}/v1/attachments`, {
    method: "POST",
    body: formData,
  });
}

async function loadProfile() {
  const data = await request(`${state.settings.auth}/v1/auth/me`);
  state.user = data;
  persistSession();
}

async function updatePresence(isOnline) {
  if (!isAuthenticated()) return;
  const data = await request(`${state.settings.auth}/v1/auth/presence`, {
    method: "POST",
    body: JSON.stringify({ is_online: isOnline }),
  });
  state.user = data;
  persistSession();
}

async function register() {
  const payload = {
    email: refs.registerEmail.value.trim(),
    password: refs.registerPassword.value,
  };

  const data = await request(`${state.settings.auth}/v1/auth/register`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.token = data.token.access_token;
  state.user = data.user;
  persistSession();
  await updatePresence(true);
  showToast(`Cuenta creada. Tu user ID es @${data.user.user_id}`, "success");
  refs.recipientUserId.focus();
  await refreshWorkspace();
}

async function login() {
  const payload = {
    identifier: refs.loginEmail.value.trim(),
    password: refs.loginPassword.value,
  };

  const data = await request(`${state.settings.auth}/v1/auth/login`, {
    method: "POST",
    body: JSON.stringify(payload),
  });

  state.token = data.token.access_token;
  state.user = data.user;
  persistSession();
  await updatePresence(true);
  showToast(`Bienvenido, @${data.user.user_id}`, "success");
  await refreshWorkspace();
}

async function fetchUserProfile(userId) {
  const normalized = userId.trim().toLowerCase();
  if (!normalized) {
    throw new Error("Debes escribir el user ID de destino.");
  }
  if (normalized === state.user.user_id) {
    state.usersById[normalized] = state.user;
    return state.user;
  }

  const data = await request(
    `${state.settings.auth}/v1/auth/users/${encodeURIComponent(normalized)}`
  );
  state.usersById[data.user_id] = data;
  return data;
}

async function lookupUser(userId) {
  const normalized = userId.trim().toLowerCase();
  if (!normalized) {
    throw new Error("Debes escribir el user ID de destino.");
  }
  if (normalized === state.user.user_id) {
    throw new Error("No puedes iniciar una conversación contigo mismo.");
  }

  return fetchUserProfile(normalized);
}

async function fetchDirectInbox() {
  if (!isAuthenticated()) return;

  const data = await request(
    `${state.settings.messaging}/v1/direct-conversations?user_id=${encodeURIComponent(
      state.user.user_id
    )}`
  );

  const items = Array.isArray(data.items) ? data.items : [];
  const peerLookups = Array.from(
    new Set(
      items
        .map((conversation) => conversation.peer_user_id)
        .filter((userId) => userId)
    )
  );

  await Promise.allSettled(peerLookups.map((userId) => fetchUserProfile(userId)));

  state.directConversations = items.map((conversation) => ({
    key: conversationKey("direct", conversation.scope_id),
    scope_type: "direct",
    scope_id: conversation.scope_id,
    peer_user_id: conversation.peer_user_id,
    title: state.usersById[conversation.peer_user_id]?.display_name || conversation.peer_user_id,
    subtitle: `@${conversation.peer_user_id}`,
    preview:
      conversation.last_message?.body ||
      getAttachmentPreviewLabel(conversation.last_message) ||
      "Todavía no hay mensajes.",
    last_message: conversation.last_message || null,
    unread_count: conversation.unread_count || 0,
    updated_at: conversation.updated_at,
    request_status: conversation.request_status || "accepted",
    requester_user_id: conversation.requester_user_id || null,
    can_send: conversation.can_send !== false,
  }));
}

async function fetchNotifications() {
  if (!isAuthenticated()) return;

  const data = await request(
    `${state.settings.notifications}/v1/notifications?user_id=${encodeURIComponent(
      state.user.user_id
    )}&limit=50`
  );
  state.notifications = Array.isArray(data.items) ? data.items : [];
  state.unreadNotificationCount = data.unread_count || 0;
  const unreadNotifications = state.notifications.filter((item) => !item.is_read);

  if (!state.notificationsInitialized) {
    for (const notification of unreadNotifications) {
      state.notificationSeenIds[notificationIdValue(notification.id)] = true;
    }
    state.notificationsInitialized = true;
  } else {
    for (const notification of unreadNotifications) {
      const notificationId = notificationIdValue(notification.id);
      if (!state.notificationSeenIds[notificationId]) {
        state.notificationSeenIds[notificationId] = true;
        enqueueNotificationToast(notification);
      }
    }
  }
}

async function fetchGroupMembers(groupId) {
  const data = await request(`${state.settings.groups}/v1/groups/${groupId}/members`);
  state.groupMembersByGroup[groupId] = Array.isArray(data) ? data : [];
  return state.groupMembersByGroup[groupId];
}

async function loadGroupDetails(groupId) {
  const detail = await request(`${state.settings.groups}/v1/groups/${groupId}`);
  const members = Array.isArray(detail.members) ? detail.members : [];
  const channels = Array.isArray(detail.channels) ? detail.channels : [];
  state.groupMembersByGroup[groupId] = members;
  state.groupChannelsByGroup[groupId] = channels;
  await Promise.allSettled(
    [
      ...members.map((member) => member.user_id),
      ...channels.flatMap((channel) =>
        Array.isArray(channel.members)
          ? channel.members.map((member) => member.user_id)
          : []
      ),
    ].map((userId) => fetchUserProfile(userId))
  );
  return detail;
}

function getGroupPreview(group) {
  const key = conversationKey("group", group.id);
  const cachedMessages = state.messagesByConversation[key] || [];
  const lastMessage = cachedMessages[cachedMessages.length - 1];
  return (
    lastMessage?.body ||
    getAttachmentPreviewLabel(lastMessage) ||
    "Grupo listo para conversar."
  );
}

function getChannelPreview(channel) {
  const key = conversationKey("channel", channel.id);
  const cachedMessages = state.messagesByConversation[key] || [];
  const lastMessage = cachedMessages[cachedMessages.length - 1];
  return (
    lastMessage?.body ||
    getAttachmentPreviewLabel(lastMessage) ||
    "Canal listo para conversar."
  );
}

function getGroupUpdatedAt(group) {
  const key = conversationKey("group", group.id);
  const cachedMessages = state.messagesByConversation[key] || [];
  const lastMessage = cachedMessages[cachedMessages.length - 1];
  return lastMessage?.created_at || group.created_at;
}

function getChannelUpdatedAt(channel) {
  const key = conversationKey("channel", channel.id);
  const cachedMessages = state.messagesByConversation[key] || [];
  const lastMessage = cachedMessages[cachedMessages.length - 1];
  return lastMessage?.created_at || channel.created_at;
}

async function fetchGroups() {
  if (!isAuthenticated()) return;

  const data = await request(`${state.settings.groups}/v1/groups/`);
  const groups = Array.isArray(data) ? data : [];

  state.groupConversations = await Promise.all(
    groups.map(async (group) => {
      const existingMembers = state.groupMembersByGroup[group.id];
      const existingChannels = state.groupChannelsByGroup[group.id];
      let members = Array.isArray(existingMembers) ? existingMembers : [];
      let channels = Array.isArray(existingChannels) ? existingChannels : [];
      if (!Array.isArray(existingMembers) || !Array.isArray(existingChannels)) {
        const detail = await loadGroupDetails(group.id).catch(() => null);
        members = Array.isArray(detail?.members) ? detail.members : members;
        channels = Array.isArray(detail?.channels) ? detail.channels : channels;
      }

      return {
        key: conversationKey("group", group.id),
        scope_type: "group",
        scope_id: group.id,
        title: group.name,
        subtitle: group.description || "Grupo",
        preview: getGroupPreview(group),
        unread_count: getUnreadNotificationsForScope("group", group.id).length,
        member_count: Array.isArray(members) ? members.length : 0,
        updated_at: getGroupUpdatedAt(group),
        channels: channels
          .filter((channel) =>
            (channel.members || []).some((member) => member.user_id === state.user.user_id)
          )
          .sort((left, right) => left.name.localeCompare(right.name))
          .map((channel) => ({
            key: conversationKey("channel", channel.id),
            scope_type: "channel",
            scope_id: channel.id,
            group_id: group.id,
            group_title: group.name,
            title: channel.name,
            subtitle: group.name,
            preview: getChannelPreview(channel),
            unread_count: getUnreadNotificationsForScope("channel", channel.id).length,
            member_count: Array.isArray(channel.members) ? channel.members.length : 0,
            members: Array.isArray(channel.members) ? channel.members : [],
            updated_at: getChannelUpdatedAt(channel),
          })),
      };
    })
  );
}

async function refreshWorkspace(options = {}) {
  const { refreshSelectedMessages = true } = options;
  if (!isAuthenticated()) {
    renderApp();
    return;
  }

  await fetchNotifications().catch(() => {
    state.notifications = [];
    state.unreadNotificationCount = 0;
  });
  await Promise.all([fetchDirectInbox(), fetchGroups()]);

  rebuildConversations();

  if (
    state.selectedConversationKey &&
    !state.conversations.some(
      (conversation) => conversation.key === state.selectedConversationKey
    )
  ) {
    state.selectedConversationKey = "";
  }

  if (!state.selectedConversationKey && state.conversations.length) {
    state.selectedConversationKey = state.conversations[0].key;
    persistUi();
  }

  if (state.groupDetailsOpen) {
    const conversation = getSelectedConversation();
    if (conversation?.scope_type === "group") {
      await loadGroupDetails(conversation.scope_id);
    }
  }

  renderApp();

  if (refreshSelectedMessages && state.selectedConversationKey) {
    await fetchMessages(state.selectedConversationKey, { markRead: true });
  }
}

async function openDirectConversation(userId) {
  const peer = await lookupUser(userId);
  const data = await request(`${state.settings.messaging}/v1/direct-conversations`, {
    method: "POST",
    body: JSON.stringify({
      user_id: state.user.user_id,
      peer_user_id: peer.user_id,
    }),
  });

  state.selectedConversationKey = conversationKey("direct", data.scope_id);
  persistUi();
  refs.recipientUserId.value = "";
  showToast(
    data.can_send
      ? `Chat listo con @${peer.user_id}`
      : `Solicitud enviada a @${peer.user_id}`,
    "info"
  );
  await refreshWorkspace({ refreshSelectedMessages: true });
}

async function acceptSelectedDirectConversation() {
  const conversation = getSelectedConversation();
  if (!conversation || conversation.scope_type !== "direct") {
    throw new Error("Selecciona una solicitud de chat directo.");
  }
  if (conversation.request_status !== "pending") {
    throw new Error("Este chat ya fue aceptado.");
  }
  if (conversation.requester_user_id === state.user.user_id) {
    throw new Error("Debes esperar a que la otra persona acepte la solicitud.");
  }

  await request(
    `${state.settings.messaging}/v1/direct-conversations/${encodeURIComponent(
      conversation.scope_id
    )}/accept`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: state.user.user_id }),
    }
  );
  showToast(`Chat aceptado con @${conversation.peer_user_id}`, "success");
  await refreshWorkspace({ refreshSelectedMessages: true });
}

async function toggleSelectedGroupDetails() {
  const conversation = getSelectedConversation();
  if (!conversation || conversation.scope_type !== "group") {
    throw new Error("Selecciona un grupo para ver sus detalles.");
  }

  state.groupDetailsOpen = !state.groupDetailsOpen;
  renderApp();
  if (!state.groupDetailsOpen) return;

  await loadGroupDetails(conversation.scope_id);
  renderApp();
}

function getSelectedGroupOrThrow() {
  const conversation = getSelectedConversation();
  if (!conversation || conversation.scope_type !== "group") {
    throw new Error("Selecciona un grupo.");
  }
  return conversation;
}

async function updateSelectedGroup() {
  const conversation = getSelectedGroupOrThrow();
  const name = refs.groupEditName.value.trim();
  const description = refs.groupEditDescription.value.trim();
  if (!name) {
    throw new Error("El nombre del grupo no puede estar vacío.");
  }

  await request(`${state.settings.groups}/v1/groups/${conversation.scope_id}`, {
    method: "PATCH",
    body: JSON.stringify({
      name,
      description,
    }),
  });
  showToast("Grupo actualizado", "success");
  await fetchGroups();
  await loadGroupDetails(conversation.scope_id);
  renderApp();
}

async function addMemberToSelectedGroup() {
  const conversation = getSelectedGroupOrThrow();
  const userId = refs.groupAddMemberInput.value.trim().toLowerCase();
  if (!userId) {
    throw new Error("Escribe el user ID que quieres añadir.");
  }
  if (userId === state.user.user_id) {
    throw new Error("Ya perteneces a este grupo.");
  }

  await fetchUserProfile(userId);
  await request(`${state.settings.groups}/v1/groups/${conversation.scope_id}/members`, {
    method: "POST",
    body: JSON.stringify({
      user_id: userId,
      role: "member",
    }),
  });
  refs.groupAddMemberInput.value = "";
  showToast(`@${userId} fue añadido al grupo`, "success");
  await fetchGroups();
  await loadGroupDetails(conversation.scope_id);
  renderApp();
}

async function removeMemberFromSelectedGroup(userId) {
  const conversation = getSelectedGroupOrThrow();
  const normalizedUserId = userId.trim().toLowerCase();
  if (!normalizedUserId) return;
  await request(
    `${state.settings.groups}/v1/groups/${conversation.scope_id}/members/${encodeURIComponent(
      normalizedUserId
    )}`,
    { method: "DELETE" }
  );
  showToast(`@${normalizedUserId} fue eliminado del grupo`, "info");
  await fetchGroups();
  await loadGroupDetails(conversation.scope_id);
  renderApp();
}

async function createChannelInSelectedGroup() {
  const conversation = getSelectedGroupOrThrow();
  const name = refs.groupChannelName.value.trim();
  const memberIds = parseCommaList(refs.groupChannelMembers.value).filter(
    (userId) => userId !== state.user.user_id
  );
  if (!name) {
    throw new Error("Escribe un nombre para el canal.");
  }

  const groupMembers = new Set(
    (state.groupMembersByGroup[conversation.scope_id] || []).map((member) => member.user_id)
  );
  for (const userId of memberIds) {
    if (!groupMembers.has(userId)) {
      throw new Error(`@${userId} debe pertenecer al grupo antes de entrar al canal.`);
    }
  }

  await request(`${state.settings.groups}/v1/groups/${conversation.scope_id}/channels`, {
    method: "POST",
    body: JSON.stringify({
      name,
      member_ids: memberIds,
    }),
  });
  refs.groupChannelName.value = "";
  refs.groupChannelMembers.value = "";
  showToast(`Canal #${name} creado`, "success");
  await loadGroupDetails(conversation.scope_id);
  await fetchGroups();
  renderApp();
}

async function addMemberToChannel(channelId, userId) {
  const conversation = getSelectedGroupOrThrow();
  const normalizedUserId = userId.trim().toLowerCase();
  if (!normalizedUserId) {
    throw new Error("Escribe el usuario que quieres añadir al canal.");
  }

  const groupMembers = new Set(
    (state.groupMembersByGroup[conversation.scope_id] || []).map((member) => member.user_id)
  );
  if (!groupMembers.has(normalizedUserId)) {
    throw new Error(`@${normalizedUserId} debe pertenecer al grupo antes de entrar al canal.`);
  }

  await request(
    `${state.settings.groups}/v1/groups/${conversation.scope_id}/channels/${encodeURIComponent(
      channelId
    )}/members`,
    {
      method: "POST",
      body: JSON.stringify({ user_id: normalizedUserId }),
    }
  );
  showToast(`@${normalizedUserId} fue añadido al canal`, "success");
  await loadGroupDetails(conversation.scope_id);
  await fetchGroups();
  renderApp();
}

async function removeMemberFromChannel(channelId, userId) {
  const conversation = getSelectedGroupOrThrow();
  const normalizedUserId = userId.trim().toLowerCase();
  if (!normalizedUserId) return;
  await request(
    `${state.settings.groups}/v1/groups/${conversation.scope_id}/channels/${encodeURIComponent(
      channelId
    )}/members/${encodeURIComponent(normalizedUserId)}`,
    { method: "DELETE" }
  );
  showToast(`@${normalizedUserId} fue eliminado del canal`, "info");
  await loadGroupDetails(conversation.scope_id);
  await fetchGroups();
  renderApp();
}

async function deleteSelectedGroup() {
  const conversation = getSelectedGroupOrThrow();
  const confirmed = window.confirm(
    `¿Eliminar el grupo "${conversation.title}"? Esta acción no se puede deshacer.`
  );
  if (!confirmed) return;

  await request(`${state.settings.groups}/v1/groups/${conversation.scope_id}`, {
    method: "DELETE",
  });
  showToast(`Grupo "${conversation.title}" eliminado`, "info");
  delete state.groupMembersByGroup[conversation.scope_id];
  delete state.groupChannelsByGroup[conversation.scope_id];
  state.groupDetailsOpen = false;
  state.selectedConversationKey = "";
  persistUi();
  await refreshWorkspace({ refreshSelectedMessages: false });
}

async function startDirectChatFromGroupMember(userId) {
  const normalizedUserId = userId.trim().toLowerCase();
  if (!normalizedUserId) return;
  await openDirectConversation(normalizedUserId);
  state.groupDetailsOpen = false;
  renderApp();
}

async function createGroupConversation() {
  const name = refs.groupName.value.trim();
  if (!name) {
    throw new Error("Debes indicar un nombre para el grupo.");
  }

  const description = refs.groupDescription.value.trim();
  const memberIds = parseCommaList(refs.groupMembersInput.value).filter(
    (userId) => userId !== state.user.user_id
  );
  if (memberIds.length < 2) {
    throw new Error("Para crear un grupo debes agregar al menos 2 usuarios.");
  }

  await Promise.all(memberIds.map((userId) => lookupUser(userId)));

  const group = await request(`${state.settings.groups}/v1/groups/`, {
    method: "POST",
    body: JSON.stringify({
      name,
      description,
      settings: {},
      member_ids: memberIds,
    }),
  });

  refs.groupName.value = "";
  refs.groupDescription.value = "";
  refs.groupMembersInput.value = "";
  state.selectedConversationKey = conversationKey("group", group.id);
  persistUi();
  showToast(`Grupo "${group.name}" creado`, "success");
  await refreshWorkspace({ refreshSelectedMessages: true });
}

async function fetchMessages(conversationKeyValue, options = {}) {
  const { markRead = false } = options;
  const conversation = state.conversations.find(
    (item) => item.key === conversationKeyValue
  );
  if (!conversation) return;

  const params = new URLSearchParams({
    scope_type: conversation.scope_type,
    scope_id: conversation.scope_id,
    limit: "200",
  });

  const data = await request(`${state.settings.messaging}/v1/messages?${params.toString()}`);
  const items = Array.isArray(data.items) ? data.items.slice() : [];
  items.sort((left, right) => {
    const leftTime = Date.parse(left.created_at || "") || 0;
    const rightTime = Date.parse(right.created_at || "") || 0;
    return leftTime - rightTime;
  });

  state.messagesByConversation[conversationKeyValue] = items;

  if (conversation.scope_type === "group" || conversation.scope_type === "channel") {
    const baseMembers =
      conversation.scope_type === "channel"
        ? conversation.members || []
        : state.groupMembersByGroup[conversation.scope_id] || [];
    const memberIds = new Set(baseMembers.map((member) => member.user_id));
    for (const message of items) {
      if (message.sender_id && !state.usersById[message.sender_id] && message.sender_id !== state.user.user_id) {
        memberIds.add(message.sender_id);
      }
    }
    await Promise.allSettled(
      [...memberIds]
        .filter((userId) => userId && !state.usersById[userId] && userId !== state.user.user_id)
        .map((userId) => fetchUserProfile(userId))
    );
  }

  renderApp();

  if (markRead) {
    const unread = items.filter((message) => {
      if (message.sender_id === state.user.user_id) return false;
      const myReceipt = (message.receipts || []).find(
        (receipt) => receipt.user_id === state.user.user_id
      );
      return myReceipt?.status !== "read";
    });

    if (unread.length) {
      await Promise.all(
        unread.map((message) =>
          request(`${state.settings.messaging}/v1/messages/${message.id}/receipts`, {
            method: "POST",
            body: JSON.stringify({
              user_id: state.user.user_id,
              status: "read",
            }),
          })
        )
      );
      await fetchMessages(conversationKeyValue, { markRead: false });
      if (conversation.scope_type === "direct") {
        await fetchDirectInbox();
      }
      renderApp();
    }
  }
}

async function markNotificationsReadForConversation(conversation) {
  if (!conversation || !isAuthenticated()) return;
  await request(
    `${state.settings.notifications}/v1/notifications/read?user_id=${encodeURIComponent(
      state.user.user_id
    )}&scope_type=${encodeURIComponent(conversation.scope_type)}&scope_id=${encodeURIComponent(
      conversation.scope_id
    )}`,
    {
      method: "POST",
      body: JSON.stringify({ notification_ids: [] }),
    }
  );
  await fetchNotifications();
}

async function sendMessage() {
  const conversation = getSelectedConversation();
  if (!conversation) {
    throw new Error("Selecciona una conversación antes de enviar.");
  }
  if (conversation.scope_type === "direct" && !conversation.can_send) {
    throw new Error("Este chat directo debe ser aceptado antes de enviar mensajes.");
  }

  const body = refs.messageInput.value.trim();
  const files = getSelectedFiles();
  if (!body && !files.length) {
    throw new Error("Escribe un mensaje o adjunta al menos un archivo.");
  }

  let participantIds = [];
  if (conversation.scope_type === "direct") {
    participantIds = [conversation.peer_user_id];
  } else if (conversation.scope_type === "channel") {
    participantIds = (conversation.members || [])
      .map((member) => member.user_id)
      .filter((userId) => userId !== state.user.user_id);
  } else {
    const members =
      state.groupMembersByGroup[conversation.scope_id] ||
      (await fetchGroupMembers(conversation.scope_id));
    participantIds = members
      .map((member) => member.user_id)
      .filter((userId) => userId !== state.user.user_id);
  }

  const uploadedAttachments = [];
  for (const file of files) {
    uploadedAttachments.push(await uploadAttachment(file, conversation));
  }

  await request(`${state.settings.messaging}/v1/messages`, {
    method: "POST",
    body: JSON.stringify({
      sender_id: state.user.user_id,
      scope_type: conversation.scope_type,
      scope_id: conversation.scope_id,
      body: body || null,
      attachment_ids: uploadedAttachments.map((attachment) => attachment.id),
      participant_ids: participantIds,
    }),
  });

  refs.messageInput.value = "";
  refs.messageFiles.value = "";
  renderSelectedFiles();
  await fetchMessages(conversation.key, { markRead: false });
  await refreshWorkspace({ refreshSelectedMessages: false });
}

function selectConversation(key) {
  const previousConversation = getSelectedConversation();
  state.selectedConversationKey = key;
  const nextConversation = getSelectedConversation();
  if (
    !nextConversation ||
    nextConversation.scope_type !== "group" ||
    previousConversation?.key !== nextConversation.key
  ) {
    state.groupDetailsOpen = false;
  }
  persistUi();
  renderApp();
  const conversation = getSelectedConversation();
  fetchMessages(key, { markRead: true }).catch((error) => {
    showToast(String(error), "error");
  });
  markNotificationsReadForConversation(conversation).catch(() => {});
}

function saveSettings() {
  state.settings = {
    auth: normalizeBaseUrl(refs.authBaseUrl.value, DEFAULT_SETTINGS.auth),
    messaging: normalizeBaseUrl(refs.messagingBaseUrl.value, DEFAULT_SETTINGS.messaging),
    groups: normalizeBaseUrl(refs.groupsBaseUrl.value, DEFAULT_SETTINGS.groups),
    notifications: normalizeBaseUrl(
      refs.notificationsBaseUrl.value,
      DEFAULT_SETTINGS.notifications
    ),
  };
  persistSettings();
  syncSettingsInputs();
  showToast("Ajustes guardados", "success");
}

async function logout() {
  if (isAuthenticated()) {
    try {
      await updatePresence(false);
    } catch (_) {
      // Ignore presence failures while closing session.
    }
  }

  state.token = "";
  state.user = null;
  state.directConversations = [];
  state.groupConversations = [];
  state.conversations = [];
  state.selectedConversationKey = "";
  state.messagesByConversation = {};
  state.usersById = {};
  state.groupMembersByGroup = {};
  state.groupChannelsByGroup = {};
  state.notifications = [];
  state.unreadNotificationCount = 0;
  state.notificationSeenIds = {};
  clearNotificationToasts();
  state.notificationsInitialized = false;
  state.groupDetailsOpen = false;
  persistSession();
  persistUi();
  renderApp();
  showToast("Sesión cerrada", "info");
}

function sendOfflinePresenceOnPageHide() {
  if (!isAuthenticated()) return;

  fetch(`${state.settings.auth}/v1/auth/presence`, {
    method: "POST",
    headers: {
      Authorization: `Bearer ${state.token}`,
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ is_online: false }),
    keepalive: true,
  }).catch(() => {});
}

function startPolling() {
  stopPolling();
  state.pollTimer = window.setInterval(async () => {
    if (!isAuthenticated()) return;
    try {
      await refreshWorkspace({ refreshSelectedMessages: false });
      if (state.selectedConversationKey) {
        await fetchMessages(state.selectedConversationKey, { markRead: false });
      }
    } catch (_) {
      // Polling is best-effort.
    }
  }, POLL_MS);
}

function stopPolling() {
  if (state.pollTimer) {
    clearInterval(state.pollTimer);
    state.pollTimer = null;
  }
}

function bindEvents() {
  window.addEventListener("pagehide", () => {
    sendOfflinePresenceOnPageHide();
  });

  refs.btnTabLogin.addEventListener("click", () => setAuthMode("login"));
  refs.btnTabRegister.addEventListener("click", () => setAuthMode("register"));

  refs.loginForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnLogin, "Entrando...", async () => {
      try {
        await login();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.registerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnRegister, "Creando...", async () => {
      try {
        await register();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.startConversationForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnStartConversation, "Abriendo...", async () => {
      try {
        await openDirectConversation(refs.recipientUserId.value);
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.createGroupForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnCreateGroup, "Creando...", async () => {
      try {
        await createGroupConversation();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupEditForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnUpdateGroup, "Guardando...", async () => {
      try {
        await updateSelectedGroup();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupAddMemberForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnAddGroupMember, "Añadiendo...", async () => {
      try {
        await addMemberToSelectedGroup();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupCreateChannelForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnCreateChannel, "Creando...", async () => {
      try {
        await createChannelInSelectedGroup();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.btnDeleteGroup.addEventListener("click", async () => {
    await runWithBusyState(refs.btnDeleteGroup, "Eliminando...", async () => {
      try {
        await deleteSelectedGroup();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupDetailsChannels.addEventListener("submit", async (event) => {
    const form = event.target.closest("[data-channel-add-form]");
    if (!form) return;
    event.preventDefault();
    const channelId = form.getAttribute("data-channel-add-form") || "";
    const input = form.querySelector("[data-channel-add-input]");
    const button = form.querySelector("button");
    await runWithBusyState(button, "Añadiendo...", async () => {
      try {
        await addMemberToChannel(channelId, input?.value || "");
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupDetailsChannels.addEventListener("click", async (event) => {
    const removeButton = event.target.closest("[data-channel-remove-user]");
    if (!removeButton) return;
    await runWithBusyState(removeButton, "Quitando...", async () => {
      try {
        await removeMemberFromChannel(
          removeButton.getAttribute("data-channel-id") || "",
          removeButton.getAttribute("data-channel-remove-user") || ""
        );
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.groupDetailsMembers.addEventListener("click", async (event) => {
    const directButton = event.target.closest("[data-direct-user]");
    if (directButton) {
      await runWithBusyState(directButton, "Abriendo...", async () => {
        try {
          await startDirectChatFromGroupMember(
            directButton.getAttribute("data-direct-user") || ""
          );
        } catch (error) {
          showToast(String(error), "error");
        }
      });
      return;
    }

    const removeButton = event.target.closest("[data-remove-user]");
    if (!removeButton) return;
    await runWithBusyState(removeButton, "Eliminando...", async () => {
      try {
        await removeMemberFromSelectedGroup(removeButton.getAttribute("data-remove-user") || "");
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.composerForm.addEventListener("submit", async (event) => {
    event.preventDefault();
    await runWithBusyState(refs.btnSendMessage, "Enviando...", async () => {
      try {
        await sendMessage();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.messageInput.addEventListener("keydown", async (event) => {
    if (!(event.ctrlKey && event.key === "Enter")) {
      return;
    }
    event.preventDefault();
    await runWithBusyState(refs.btnSendMessage, "Enviando...", async () => {
      try {
        await sendMessage();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.messageFiles.addEventListener("change", () => renderSelectedFiles());

  refs.btnRefreshInbox.addEventListener("click", async () => {
    await runWithBusyState(refs.btnRefreshInbox, "Actualizando...", async () => {
      try {
        await refreshWorkspace({ refreshSelectedMessages: true });
        showToast("Bandeja actualizada", "info");
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.btnLogout.addEventListener("click", async () => {
    await runWithBusyState(refs.btnLogout, "Saliendo...", async () => {
      try {
        await logout();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });

  refs.btnOpenSettings.addEventListener("click", () => openSettingsDrawer(true));
  refs.btnCloseSettings.addEventListener("click", () => openSettingsDrawer(false));
  refs.drawerBackdrop.addEventListener("click", () => openSettingsDrawer(false));

  refs.btnSaveSettings.addEventListener("click", () => saveSettings());
  refs.btnClearOutput.addEventListener("click", () => setOutput("Aún no hay respuestas."));
  refs.btnAcceptDirect.addEventListener("click", async () => {
    await runWithBusyState(refs.btnAcceptDirect, "Aceptando...", async () => {
      try {
        await acceptSelectedDirectConversation();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
  });
  refs.btnGroupDetails.addEventListener("click", async () => {
    await runWithBusyState(refs.btnGroupDetails, "Cargando...", async () => {
      try {
        await toggleSelectedGroupDetails();
      } catch (error) {
        showToast(String(error), "error");
      }
    });
    renderApp();
  });
}

async function restoreSessionIfPossible() {
  if (!state.token) return;

  try {
    await loadProfile();
    await updatePresence(true);
    await refreshWorkspace({ refreshSelectedMessages: true });
  } catch (_) {
    state.token = "";
    state.user = null;
    persistSession();
  }
}

async function bootstrap() {
  cacheRefs();
  refs.notificationWidget.style.setProperty(
    "--notification-widget-duration",
    `${NOTIFICATION_WIDGET_MS}ms`
  );
  loadPersistedState();
  syncSettingsInputs();
  setOutput("Aún no hay respuestas.");
  setAuthMode(state.authMode);
  bindEvents();
  renderApp();
  await restoreSessionIfPossible();
  renderApp();
  startPolling();
}

bootstrap();
