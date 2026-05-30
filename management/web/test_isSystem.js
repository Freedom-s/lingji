// 在浏览器控制台运行这个测试
import { useUserStore } from '@/pinia/stores/user'

const userStore = useUserStore()
console.log('isSystem:', userStore.isSystem)
console.log('isSuperuser:', userStore.isSuperuser)
console.log('routes:', import('@/pinia/stores/permission').usePermissionStore().routes)
