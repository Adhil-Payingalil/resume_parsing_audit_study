import requests
import time

def test_script_injection(url):
    """
    Test JINA AI with script injection to handle dynamic content loading
    """
    
    jina_url = f"https://r.jina.ai/{url}"
    
    # Test different script injection approaches
    scripts = [
        {
            "name": "Basic scroll simulation",
            "script": "document.addEventListener('mutationIdle', window.simulateScroll);"
        },
        {
            "name": "Wait for content to load",
            "script": """
                // Wait for page to be fully loaded
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', function() {
                        setTimeout(function() {
                            window.contentLoaded = true;
                        }, 2000);
                    });
                } else {
                    setTimeout(function() {
                        window.contentLoaded = true;
                    }, 2000);
                }
            """
        },
        {
            "name": "Scroll and wait for lazy loading",
            "script": """
                // Simulate scrolling to trigger lazy loading
                function simulateScroll() {
                    window.scrollTo(0, document.body.scrollHeight);
                    setTimeout(function() {
                        window.scrollTo(0, 0);
                    }, 1000);
                }
                
                // Execute after page load
                if (document.readyState === 'loading') {
                    document.addEventListener('DOMContentLoaded', simulateScroll);
                } else {
                    simulateScroll();
                }
            """
        }
    ]
    
    print(f"Testing script injection for: {url}")
    print("=" * 80)
    
    for i, script_config in enumerate(scripts, 1):
        print(f"\n{i}. {script_config['name']}")
        print("-" * 40)
        
        headers = {
            "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
            "X-Wait-For-Selector": "body",
            "X-Wait-For-Timeout": "10000",
            "x-timeout": "60",
            "Content-Type": "application/x-www-form-urlencoded"
        }
        
        data = f"injectPageScript={script_config['script']}"
        
        try:
            start_time = time.time()
            
            response = requests.post(
                jina_url,
                headers=headers,
                data=data,
                timeout=70
            )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {duration:.2f} seconds")
            print(f"Content Length: {len(response.text)} characters")
            
            if response.status_code == 200:
                content = response.text.lower()
                
                # Check for job-related content
                job_keywords = ['job', 'position', 'role', 'description', 'requirements', 'qualifications']
                found_keywords = [kw for kw in job_keywords if kw in content]
                
                if found_keywords:
                    print(f"✅ Found job keywords: {', '.join(found_keywords)}")
                else:
                    print("⚠️ No job-related keywords found")
                
                # Show preview
                preview = response.text[:300].replace('\n', ' ')
                print(f"Preview: {preview}...")
                
            else:
                print(f"❌ Request failed: {response.text[:200]}...")
                
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()

def test_without_script_injection(url):
    """
    Test the same URL without script injection for comparison
    """
    jina_url = f"https://r.jina.ai/{url}"
    
    print("Comparison: Without script injection")
    print("-" * 40)
    
    headers = {
        "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
        "X-Wait-For-Selector": "body",
        "X-Wait-For-Timeout": "5000",
        "x-timeout": "60"
    }
    
    try:
        start_time = time.time()
        
        response = requests.get(
            jina_url,
            headers=headers,
            timeout=70
        )
        
        end_time = time.time()
        duration = end_time - start_time
        
        print(f"Status Code: {response.status_code}")
        print(f"Response Time: {duration:.2f} seconds")
        print(f"Content Length: {len(response.text)} characters")
        
        if response.status_code == 200:
            content = response.text.lower()
            job_keywords = ['job', 'position', 'role', 'description', 'requirements', 'qualifications']
            found_keywords = [kw for kw in job_keywords if kw in content]
            
            if found_keywords:
                print(f"✅ Found job keywords: {', '.join(found_keywords)}")
            else:
                print("⚠️ No job-related keywords found")
            
            preview = response.text[:300].replace('\n', ' ')
            print(f"Preview: {preview}...")
            
        else:
            print(f"❌ Request failed: {response.text[:200]}...")
            
    except Exception as e:
        print(f"❌ Error: {e}")

if __name__ == "__main__":
    test_url = "https://kevgroup.com/open-positions/?gh_jid=4859774007&gh_src=my.greenhouse.search"
    
    # Test without script injection first
    test_without_script_injection(test_url)
    
    print("\n" + "="*80 + "\n")
    
    # Test with script injection
    test_script_injection(test_url)
