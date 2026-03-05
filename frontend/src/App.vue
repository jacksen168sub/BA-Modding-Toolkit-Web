<template>
  <div id="app">
    <el-container>
      <el-header>
        <NavBar />
      </el-header>
      <el-main>
        <router-view />
      </el-main>
      <el-footer>
        <Footer />
      </el-footer>
    </el-container>
  </div>
</template>

<script setup>
import NavBar from '@/components/NavBar.vue'
import Footer from '@/components/Footer.vue'
</script>

<style>
#app {
  min-height: 100vh;
  display: flex;
  flex-direction: column;
}

.el-container {
  flex: 1;
}

.el-header {
  padding: 0;
  height: auto !important;
}

.el-main {
  padding: 20px;
  background-color: #f5f7fa;
}

.el-footer {
  padding: 0;
  height: auto !important;
}
</style>
