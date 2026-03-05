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
    path: '/tasks',
    name: 'Tasks',
    component: () => import('@/pages/Tasks.vue')
  }
]

const router = createRouter({
  history: createWebHistory(),
  routes
})

export default router
