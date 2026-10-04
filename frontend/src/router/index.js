// SPDX-License-Identifier: GPL-3.0-or-later
// Copyright (C) 2026 jacksen168sub

import { createRouter, createWebHistory } from 'vue-router'

const routes = [
  {
    path: '/',
    name: 'Home',
    component: () => import('@/pages/Home.vue')
  },
  {
    path: '/update',
    name: 'Update',
    component: () => import('@/pages/Update.vue')
  },
  {
    path: '/pack',
    name: 'Pack',
    component: () => import('@/pages/Pack.vue')
  },
  {
    path: '/extract',
    name: 'Extract',
    component: () => import('@/pages/Extract.vue')
  },
  {
    path: '/crc',
    name: 'Crc',
    component: () => import('@/pages/Crc.vue')
  },
  {
    path: '/parse',
    name: 'Parse',
    component: () => import('@/pages/Parse.vue')
  },
  {
    path: '/spine-preview',
    name: 'SpinePreview',
    component: () => import('@/pages/SpinePreview.vue')
  },
  {
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/pages/Tasks.vue')
  },
  {
    path: '/status',
    name: 'Status',
    component: () => import('@/pages/Status.vue')
  },
  {
    path: '/settings',
    name: 'Settings',
    component: () => import('@/pages/Settings.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

// Extension point for HTML an operator injects into the page (see "Custom page injection"
// in the README). This is a single-page app, so in-app navigation never reloads the
// document — this fires on every route change so injected content can react to it.
// `fullPath` can carry a taskId query; use `path` if the consumer must not receive it.
router.afterEach((to) => {
  window.__bamtRouteChange?.({ path: to.path, fullPath: to.fullPath })
})

export default router
