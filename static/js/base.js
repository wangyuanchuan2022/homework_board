// 存储登录状态到cookie
        function setCookie(name, value, days) {
            var expires = "";
            if (days) {
                var date = new Date();
                date.setTime(date.getTime() + (days * 24 * 60 * 60 * 1000));
                expires = "; expires=" + date.toUTCString();
            }
            document.cookie = name + "=" + (value || "") + expires + "; path=/";
        }

        // 获取cookie值
        function getCookie(name) {
            var nameEQ = name + "=";
            var ca = document.cookie.split(';');
            for(var i=0; i < ca.length; i++) {
                var c = ca[i];
                while (c.charAt(0) == ' ') c = c.substring(1, c.length);
                if (c.indexOf(nameEQ) == 0) return c.substring(nameEQ.length, c.length);
            }
            return null;
        }

        // 删除cookie
        function eraseCookie(name) {
            document.cookie = name + '=; Max-Age=-99999999;';
        }

        // 背景图片缓存功能
        const bgCache = {
            // 缓存版本，更新图片时递增此版本号
            version: 1,
            
            // 初始化已完成标志
            initialized: false,
            
            // 初始化IndexedDB
            async initDB() {
                return new Promise((resolve, reject) => {
                    if (this.db) {
                        resolve(this.db);
                        return;
                    }
                    
                    if (!window.indexedDB) {
                        console.warn('浏览器不支持IndexedDB，将回退到无缓存模式');
                        reject(new Error('IndexedDB不可用'));
                        return;
                    }
                    
                    const request = indexedDB.open('BackgroundCache', 1);
                    
                    request.onupgradeneeded = (event) => {
                        const db = event.target.result;
                        if (!db.objectStoreNames.contains('images')) {
                            db.createObjectStore('images', { keyPath: 'key' });
                        }
                    };
                    
                    request.onsuccess = (event) => {
                        const db = event.target.result;
                        this.db = db;
                        
                        // 处理数据库连接意外关闭
                        db.onclose = () => {
                            console.warn('IndexedDB连接意外关闭');
                            this.db = null;
                        };
                        
                        // 处理版本变更
                        db.onversionchange = (event) => {
                            db.close();
                            console.warn('IndexedDB版本已变更，需要重新加载页面');
                            this.db = null;
                            alert('应用已更新，请刷新页面以应用更改');
                        };
                        
                        resolve(db);
                    };
                    
                    request.onerror = (event) => {
                        console.error('打开IndexedDB失败:', event.target.error);
                        reject(event.target.error);
                    };
                    
                    // 处理数据库被阻塞
                    request.onblocked = (event) => {
                        console.warn('IndexedDB操作被阻塞，请关闭其他标签页后重试');
                        alert('数据库操作被阻塞，请关闭其他打开的相同网站标签页，然后刷新此页面');
                        reject(new Error('数据库被阻塞'));
                    };
                });
            },
            
            // 从IndexedDB保存图片数据
            async saveToIndexedDB(key, dataUrl) {
                try {
                    const db = await this.initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(['images'], 'readwrite');
                        const store = transaction.objectStore('images');
                        
                        const item = {
                            key: `bg_cache_${key}`,
                            data: dataUrl,
                            version: this.version,
                            timestamp: Date.now()
                        };
                        
                        const request = store.put(item);
                        
                        request.onsuccess = () => resolve(true);
                        request.onerror = (e) => {
                            console.error('保存到IndexedDB失败:', e.target.error);
                            reject(e.target.error);
                        };
                        
                        // 添加事务完成事件处理
                        transaction.oncomplete = () => {
                            console.log(`图片 ${key} 保存事务完成`);
                            resolve(true);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error(`保存图片 ${key} 事务失败:`, event.target.error);
                            reject(event.target.error);
                        };
                        
                        transaction.onabort = (event) => {
                            console.warn(`保存图片 ${key} 事务被中止:`, event);
                            reject(new Error('事务被中止'));
                        };
                    });
                } catch (error) {
                    console.error('IndexedDB操作失败:', error);
                    return false;
                }
            },
            
            // 从IndexedDB读取图片数据
            async getFromIndexedDB(key) {
                try {
                    const db = await this.initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(['images'], 'readonly');
                        const store = transaction.objectStore('images');
                        const request = store.get(`bg_cache_${key}`);
                        
                        let result = null;
                        
                        request.onsuccess = (event) => {
                            result = event.target.result;
                            if (!result) {
                                return; // 让事务完成时再处理
                            }
                            
                            // 检查版本是否匹配
                            if (result.version !== this.version) {
                                // 标记需要删除，但在事务完成后再删除
                                result = null;
                                return;
                            }
                            
                            // 检查是否过期（7天）
                            const now = Date.now();
                            const sevenDays = 7 * 24 * 60 * 60 * 1000;
                            if (now - result.timestamp > sevenDays) {
                                // 标记需要删除，但在事务完成后再删除
                                result = null;
                                return;
                            }
                        };
                        
                        request.onerror = (event) => {
                            console.error('从IndexedDB读取失败:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        // 使用事务完成事件来处理结果
                        transaction.oncomplete = () => {
                            if (!result) {
                                // 如果需要删除过期条目，在新事务中执行
                                if (result === null) {
                                    this.removeFromIndexedDB(key).catch(console.error);
                                }
                                resolve(null);
                                return;
                            }
                            resolve(result.data);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error('读取事务错误:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        transaction.onabort = (event) => {
                            console.warn('读取事务被中止:', event);
                            reject(new Error('事务被中止'));
                        };
                    });
                } catch (error) {
                    console.error('IndexedDB操作失败:', error);
                    return null;
                }
            },
            
            // 从IndexedDB删除图片
            async removeFromIndexedDB(key) {
                try {
                    const db = await this.initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(['images'], 'readwrite');
                        const store = transaction.objectStore('images');
                        const request = store.delete(`bg_cache_${key}`);
                        
                        request.onsuccess = () => {
                            console.log(`删除缓存项 ${key} 操作成功`);
                        };
                        
                        request.onerror = (event) => {
                            console.error('从IndexedDB删除失败:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        // 使用事务完成事件来确认操作
                        transaction.oncomplete = () => {
                            console.log(`删除缓存项 ${key} 事务完成`);
                            resolve(true);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error('删除事务错误:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        transaction.onabort = (event) => {
                            console.warn('删除事务被中止:', event);
                            reject(new Error('事务被中止'));
                        };
                    });
                } catch (error) {
                    console.error('IndexedDB操作失败:', error);
                    return false;
                }
            },
            
            // 将图片URL转换为base64编码的Data URL并存储
            async cacheImage(url, key) {
                // 检查是否已有此图片的有效缓存
                const cached = await this.getFromCache(key);
                if (cached) return cached;
                
                try {
                    // 加载图片并转换为Data URL
                    const response = await fetch(url, {
                        // 添加缓存策略，优先使用缓存，加快加载速度
                        cache: 'force-cache',
                        priority: 'high'
                    });
                    const blob = await response.blob();
                    return new Promise((resolve, reject) => {
                        const reader = new FileReader();
                        reader.onload = async () => {
                            const dataUrl = reader.result;
                            
                            try {
                                // 尝试使用IndexedDB存储
                                await this.saveToIndexedDB(key, dataUrl);
                                console.log(`图片 ${key} 已缓存到IndexedDB`);
                                resolve(dataUrl);
                            } catch (dbError) {
                                console.warn('存储到IndexedDB失败，回退到无缓存模式:', dbError);
                                resolve(url); // 出错时返回原始URL
                            }
                        };
                        reader.onerror = (e) => {
                            console.error('读取图片失败:', e);
                            reject(e);
                        };
                        reader.readAsDataURL(blob);
                    });
                } catch (error) {
                    console.error('缓存图片失败:', error);
                    return url; // 出错时返回原始URL
                }
            },
            
            // 从缓存获取图片
            async getFromCache(key) {
                try {
                    // 尝试从IndexedDB获取
                    const idbData = await this.getFromIndexedDB(key);
                    if (idbData) {
                        return idbData;
                    }
                    
                    return null;
                } catch (error) {
                    console.error('读取缓存失败:', error);
                    return null;
                }
            },
            
            // 预加载并缓存所有背景图片
            async preloadBackgrounds() {
                const preloadImage = async (url, key) => {
                    try {
                        await this.cacheImage(url, key);
                        console.log(`背景图片 ${key} 预加载完成`);
                        return true;
                    } catch (error) {
                        console.error(`背景图片 ${key} 预加载失败:`, error);
                        return false;
                    }
                };
                
                try {
                    // 逐个加载背景图片，即使某个失败也继续加载其他的
                    const results = await Promise.allSettled([
                        preloadImage(staticBgImg1, 'bg1'),
                        preloadImage(staticBgImg2, 'bg2'),
                        preloadImage(staticBgImg3, 'bg3'),
                        preloadImage(staticBgImg4, 'bg4')
                    ]);
                    
                    const successful = results.filter(r => r.status === 'fulfilled' && r.value === true).length;
                    console.log(`背景图片预加载完成: ${successful}/4 成功`);
                } catch (error) {
                    console.error('预加载背景图片过程中发生错误:', error);
                }
            },
            
            // 使用缓存的图片作为背景，如果没有缓存则使用原始URL
            async applyBackground(url, cacheKey) {
                try {
                    // 先尝试从缓存获取
                    let bgUrl = await this.getFromCache(cacheKey);
                    if (!bgUrl) {
                        // 没有缓存，加载并缓存
                        bgUrl = await this.cacheImage(url, cacheKey);
                    }
                    document.body.style.backgroundImage = `url("${bgUrl}")`;
                    return bgUrl;
                } catch (error) {
                    console.error('应用背景失败，使用原始URL:', error);
                    document.body.style.backgroundImage = `url("${url}")`;
                    return url;
                }
            },
            
            // 清除所有背景图片缓存
            async clearCache() {
                try {
                    // 清除IndexedDB中的缓存
                    const db = await this.initDB();
                    return new Promise((resolve, reject) => {
                        const transaction = db.transaction(['images'], 'readwrite');
                        const store = transaction.objectStore('images');
                        const request = store.clear();
                        
                        request.onsuccess = () => {
                            console.log('清除缓存操作成功');
                        };
                        
                        request.onerror = (event) => {
                            console.error('清除IndexedDB缓存失败:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        // 使用事务完成事件来确认操作
                        transaction.oncomplete = () => {
                            console.log('清除缓存事务完成');
                            resolve(true);
                        };
                        
                        transaction.onerror = (event) => {
                            console.error('清除缓存事务错误:', event.target.error);
                            reject(event.target.error);
                        };
                        
                        transaction.onabort = (event) => {
                            console.warn('清除缓存事务被中止:', event);
                            reject(new Error('事务被中止'));
                        };
                    });
                } catch (error) {
                    console.error('清除缓存操作失败:', error);
                    return false;
                }
            },
            
            // 优先加载背景图片，不等待DOM加载完成
            init: function() {
                if (this.initialized) return;
                this.initialized = true;
                
                // 立即开始初始化IndexedDB
                this.initDB().catch(err => console.warn('IndexedDB初始化失败:', err));
                
                // 立即开始加载保存的背景
                const savedBgKey = localStorage.getItem('selectedBackground');
                const savedBgUrl = localStorage.getItem('selectedBackgroundUrl');
                
                if (savedBgKey && savedBgKey !== 'none' && savedBgUrl) {
                    this.applyBackground(savedBgUrl, savedBgKey)
                        .then(() => {
                            document.body.classList.remove('no-bg-selected');
                            console.log('背景已从缓存加载');
                        })
                        .catch(error => {
                            console.error('从缓存加载背景失败:', error);
                            // 失败时尝试直接使用原始URL
                            document.body.style.backgroundImage = `url("${savedBgUrl}")`;
                            document.body.classList.remove('no-bg-selected');
                        });
                }
                
                // 在后台预加载所有背景图片
                setTimeout(() => {
                    this.preloadBackgrounds().catch(error => {
                        console.warn('背景预加载失败，将在需要时加载:', error);
                    });
                }, 1000); // 延迟1秒开始预加载，优先处理用户选择的背景
            }
        };

        // 立即初始化背景缓存，不等待DOMContentLoaded
        bgCache.init();
        
        // 懒加载图片
        document.addEventListener('DOMContentLoaded', function() {
            var lazyImages = [].slice.call(document.querySelectorAll('img.lazy'));

            if ('IntersectionObserver' in window) {
                let lazyImageObserver = new IntersectionObserver(function(entries, observer) {
                    entries.forEach(function(entry) {
                        if (entry.isIntersecting) {
                            let lazyImage = entry.target;
                            lazyImage.src = lazyImage.dataset.src;
                            lazyImage.classList.remove('lazy');
                            lazyImage.classList.remove('skeleton-loader');
                            lazyImageObserver.unobserve(lazyImage);
                        }
                    });
                });

                lazyImages.forEach(function(lazyImage) {
                    lazyImageObserver.observe(lazyImage);
                });
            }
        });

        // 背景选择器功能
        document.addEventListener('DOMContentLoaded', function() {
            const bgSelectorBtn = document.getElementById('bgSelectorBtn');
            const bgSelectorContent = document.getElementById('bgSelectorContent');
            const bgOptions = document.querySelectorAll('.bg-option');
            const uploadBgBtn = document.getElementById('uploadBgBtn');
            const bgImageUpload = document.getElementById('bgImageUpload');
            const debugInfo = document.getElementById('debug-info');
            const setDefaultBg = document.getElementById('setDefaultBg');

            // 调试信息显示
            function showDebug(message) {
                debugInfo.style.display = 'block';
                debugInfo.innerHTML = message;
            }
            
            // 设置对应的背景选项为激活状态
            const savedBgUrl = localStorage.getItem('selectedBackgroundUrl');
            if (savedBgUrl) {
                bgOptions.forEach(option => {
                    const bgValue = option.dataset.bg;
                    if (bgValue === savedBgUrl) {
                        bgOptions.forEach(opt => opt.classList.remove('active'));
                        option.classList.add('active');
                        showDebug('使用保存的背景: ' + bgValue.substring(0, 30) + '...');
                    }
                });
            }

            // 直接设置背景按钮
            if (setDefaultBg) {
                setDefaultBg.addEventListener('click', async function() {
                    try {
                        await bgCache.applyBackground(staticBgImg1, 'bg1');
                        document.body.classList.remove('no-bg-selected');
                        localStorage.setItem('selectedBackground', 'bg1');
                        localStorage.setItem('selectedBackgroundUrl', staticBgImg1);
                        showDebug('已直接应用背景图（已缓存）');
                    } catch (error) {
                        console.error('应用背景失败:', error);
                        showDebug('应用背景失败，请重试');
                    }
                });
            }

            // 切换背景选择器面板
            bgSelectorBtn.addEventListener('click', function() {
                bgSelectorContent.classList.toggle('active');
            });

            // 点击外部关闭背景选择器
            document.addEventListener('click', function(event) {
                if (!bgSelectorContent.contains(event.target) &&
                    !bgSelectorBtn.contains(event.target) &&
                    bgSelectorContent.classList.contains('active')) {
                    bgSelectorContent.classList.remove('active');
                }
            });

            // 选择背景
            bgOptions.forEach((option, index) => {
                option.addEventListener('click', function() {
                    if (this.id === 'uploadBgBtn') return;

                    // 更新激活状态
                    bgOptions.forEach(opt => opt.classList.remove('active'));
                    this.classList.add('active');

                    const bgValue = this.dataset.bg;
                    showDebug('选择背景: ' + bgValue);

                    if (bgValue === 'none') {
                        document.body.style.backgroundImage = '';
                        document.body.classList.add('no-bg-selected');
                        localStorage.removeItem('selectedBackground');
                        localStorage.removeItem('selectedBackgroundUrl');
                    } else {
                        // 为预定义的背景图使用缓存
                        const bgKey = `bg${index}`;
                        showDebug('正在加载背景...');
                        bgCache.applyBackground(bgValue, bgKey)
                            .then(() => {
                                document.body.classList.remove('no-bg-selected');
                                localStorage.setItem('selectedBackground', bgKey);
                                localStorage.setItem('selectedBackgroundUrl', bgValue);
                                showDebug('背景已应用（使用缓存）');
                            })
                            .catch(error => {
                                console.error('应用背景失败:', error);
                                // 失败时尝试直接使用
                                document.body.style.backgroundImage = `url("${bgValue}")`;
                                document.body.classList.remove('no-bg-selected');
                                localStorage.setItem('selectedBackground', bgKey);
                                localStorage.setItem('selectedBackgroundUrl', bgValue);
                                showDebug('背景已应用（使用原始URL）');
                            });
                    }
                });
            });

            // 上传自定义背景
            uploadBgBtn.addEventListener('click', function() {
                bgImageUpload.click();
            });

            bgImageUpload.addEventListener('change', function() {
                const file = this.files[0];
                if (file) {
                    const reader = new FileReader();
                    reader.onload = function(e) {
                        const imgUrl = e.target.result;
                        showDebug('上传图片成功（已自动缓存）');

                        // 创建新的背景选项
                        const newOption = document.createElement('div');
                        newOption.className = 'bg-option';
                        newOption.dataset.bg = imgUrl;
                        newOption.style.backgroundImage = 'url("' + imgUrl + '")';

                        // 插入到上传按钮前
                        uploadBgBtn.parentNode.insertBefore(newOption, uploadBgBtn);

                        // 添加点击事件
                        newOption.addEventListener('click', function() {
                            bgOptions.forEach(opt => opt.classList.remove('active'));
                            this.classList.add('active');
                            
                            // 用户上传的图片已经是Data URL，直接使用
                            document.body.style.backgroundImage = 'url("' + imgUrl + '")';
                            document.body.classList.remove('no-bg-selected');
                            
                            // 使用custom前缀标识自定义背景
                            const customKey = 'custom_' + Date.now();
                            localStorage.setItem('selectedBackground', customKey);
                            localStorage.setItem('selectedBackgroundUrl', imgUrl);
                            
                            // 单独缓存自定义图片
                            localStorage.setItem(`bg_cache_${customKey}`, JSON.stringify({
                                version: bgCache.version,
                                data: imgUrl,
                                timestamp: Date.now()
                            }));
                        });

                        // 自动点击新选项
                        newOption.click();
                    };
                    reader.readAsDataURL(file);
                }
            });
            
            // 添加清除缓存按钮（可选，用于调试）
            const clearCacheBtn = document.createElement('button');
            clearCacheBtn.className = 'btn btn-sm btn-outline-danger mt-2';
            clearCacheBtn.innerText = '清除背景缓存';
            clearCacheBtn.addEventListener('click', function() {
                showDebug('正在清除缓存...');
                bgCache.clearCache()
                    .then(() => {
                        showDebug('背景缓存已清除，刷新页面后将重新加载');
                    })
                    .catch(error => {
                        console.error('清除缓存失败:', error);
                        showDebug('清除缓存失败');
                    });
            });
            
            // 添加到背景选择器面板
            const btnContainer = document.querySelector('.bg-selector-content .mt-2.d-grid');
            if (btnContainer) {
                btnContainer.appendChild(document.createElement('hr'));
                btnContainer.appendChild(clearCacheBtn);
            }
        });

        // 按钮涟漪效果
        document.addEventListener('DOMContentLoaded', function() {
            const buttons = document.querySelectorAll('.btn');
            buttons.forEach(btn => {
                btn.addEventListener('mousedown', function(e) {
                    const x = e.pageX - this.offsetLeft;
                    const y = e.pageY - this.offsetTop;

                    const ripple = document.createElement('span');
                    ripple.classList.add('ripple');
                    ripple.style.left = x + 'px';
                    ripple.style.top = y + 'px';

                    this.appendChild(ripple);

                    setTimeout(() => {
                        ripple.remove();
                    }, 600);
                });
            });
        });