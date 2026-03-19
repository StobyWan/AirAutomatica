import { defineStore } from 'pinia'
import { ref } from 'vue'

export const useVehicleStore = defineStore('vehicle', () => {
  const controlOwner = ref<string | null>(null)
  const lastControlSeq = ref(0)

  function setControlOwner(owner: string | null) {
    controlOwner.value = owner
  }

  function updateSeq(seq: number) {
    lastControlSeq.value = seq
  }

  return { controlOwner, lastControlSeq, setControlOwner, updateSeq }
})
