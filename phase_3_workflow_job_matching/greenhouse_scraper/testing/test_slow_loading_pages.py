import requests
import time
import json

def test_jina_ai_with_wait_options(url):
    """
    Test JINA AI Reader API with various wait and timeout options
    for handling slow-loading pages (2+ seconds)
    """
    
    # Test different configurations
    test_configs = [
        {
            "name": "Basic with increased timeout",
            "headers": {
                "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
                "x-timeout": "60"
            }
        },
        {
            "name": "Wait for body selector",
            "headers": {
                "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
                "X-Wait-For-Selector": "body",
                "X-Wait-For-Timeout": "5000",
                "x-timeout": "60"
            }
        },
        {
            "name": "Wait for job content selector",
            "headers": {
                "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
                "X-Wait-For-Selector": ".content, .job-description, main, [role='main']",
                "X-Wait-For-Timeout": "10000",  # 10 seconds
                "x-timeout": "60"
            }
        },
        {
            "name": "With script injection for dynamic content",
            "headers": {
                "Authorization": "Bearer jina_41a854a487304054bf61d7b4c8565110rxtedNhsQ3HvHynxIaqvhYP1K7on",
                "X-Wait-For-Selector": "body",
                "X-Wait-For-Timeout": "5000",
                "x-timeout": "60",
                "Content-Type": "application/x-www-form-urlencoded"
            },
            "data": "injectPageScript=document.addEventListener('mutationIdle', window.simulateScroll);"
        }
    ]
    
    jina_url = f"https://r.jina.ai/{url}"
    
    print(f"Testing URL: {url}")
    print(f"JINA URL: {jina_url}")
    print("=" * 80)
    
    for i, config in enumerate(test_configs, 1):
        print(f"\n{i}. {config['name']}")
        print("-" * 40)
        
        try:
            start_time = time.time()
            
            if 'data' in config:
                # Use POST with data for script injection
                response = requests.post(
                    jina_url, 
                    headers=config['headers'], 
                    data=config['data'],
                    timeout=70
                )
            else:
                # Use GET request
                response = requests.get(
                    jina_url, 
                    headers=config['headers'], 
                    timeout=70
                )
            
            end_time = time.time()
            duration = end_time - start_time
            
            print(f"Status Code: {response.status_code}")
            print(f"Response Time: {duration:.2f} seconds")
            print(f"Content Length: {len(response.text)} characters")
            
            if response.status_code == 200:
                # Check if content looks good
                content = response.text.lower()
                if any(keyword in content for keyword in ['job', 'position', 'role', 'description', 'requirements']):
                    print("✅ Content appears to contain job-related information")
                else:
                    print("⚠️ Content may not contain expected job information")
                
                # Show first 200 characters
                print(f"Preview: {response.text[:200]}...")
                
            else:
                print(f"❌ Request failed: {response.text}")
                
        except requests.exceptions.Timeout:
            print("❌ Request timed out")
        except Exception as e:
            print(f"❌ Error: {e}")
        
        print()

def test_multiple_urls():
    """
    Test with multiple URLs to see which configuration works best
    """
    test_urls = [
        "https://kevgroup.com/open-positions/?gh_jid=4859774007&gh_src=my.greenhouse.search",
        "https://job-boards.greenhouse.io/partnerstack/jobs/4607080005?gh_src=my.greenhouse.search"
    ]
    
    for url in test_urls:
        test_jina_ai_with_wait_options(url)
        print("\n" + "="*80 + "\n")

if __name__ == "__main__":
    # Test with a specific URL
    test_url = "https://kevgroup.com/open-positions/?gh_jid=4859774007&gh_src=my.greenhouse.search"
    test_jina_ai_with_wait_options(test_url)
    
    # Uncomment to test multiple URLs
    # test_multiple_urls()
