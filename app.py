import requests
from urllib.parse import urlparse
import xml.etree.ElementTree as ET
import pandas as pd
import streamlit as st

headers = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/79.0.3945.130 Safari/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Cache-Control": "no-cache",
    "Accept-Encoding": "gzip",
    "Pragma": "no-cache"
}

def analyze_sitemap_index(sitemap_index_url):
    """Analyze the Sitemap Index file and extract the URLs of the Sitemaps."""
    
    response = requests.get(sitemap_index_url, headers=headers)
    response.raise_for_status()  # Check for errors

    root = ET.fromstring(response.content)

    namespaces = {
        'sm': 'http://www.sitemaps.org/schemas/sitemap/0.9',
        'xsi': 'http://www.w3.org/2001/XMLSchema-instance'
    }

    locs = []
    
    # Check if it's a sitemap index
    if root.tag.endswith('sitemapindex'):
        locs = [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    # Check if it's a regular sitemap
    elif root.tag.endswith('urlset'):
        locs = [loc.text for loc in root.findall('.//sm:loc', namespaces)]
    else:
        print("Unknown sitemap format")
    
    return locs

def analyze_sitemap(sitemap_url):
    """Analyze the Sitemap file, count the number of URLs, and extract the top-level directory and its URL count."""

    response = requests.get(sitemap_url, headers=headers)
    response.raise_for_status()

    root = ET.fromstring(response.content)

    url_count = 0
    top_level_directories = {}
    urls = []

    for url_elem in root.findall('{http://www.sitemaps.org/schemas/sitemap/0.9}url'):
        loc_elem = url_elem.find('{http://www.sitemaps.org/schemas/sitemap/0.9}loc')
        if loc_elem is not None:
            url_count += 1
            urls.append(loc_elem.text)
            parsed_url = urlparse(loc_elem.text)
            path_parts = parsed_url.path.split('/')
            if parsed_url.path == "/" or parsed_url.path == "":
                top_level_dir = "Homepage"
            elif len(path_parts) == 2:
                top_level_dir = "Others"
            else:
                top_level_dir = path_parts[1]  # Extract top-level directory
            if top_level_dir in top_level_directories:
                top_level_directories[top_level_dir] += 1
            else:
                top_level_directories[top_level_dir] = 1

    return url_count, top_level_directories, urls


# Streamlit app
st.title("Overdose Sitemap Analyzer")
st.markdown(
    "<p style='color:gray;'>Developed by Darren Huang. If you have any questions or found a bug, please feel free to reach out!</p>",
    unsafe_allow_html=True
)

analysis_type = st.radio("Choose analysis type:", ("Sitemap Index", "Sitemap File"))

if analysis_type == "Sitemap Index":
    sitemap_index_url = st.text_input("Enter the Sitemap Index URL:")
    if st.button("Run Analysis"):
        if sitemap_index_url:
            try:
                sitemaps = analyze_sitemap_index(sitemap_index_url)
                st.write(f"Found {len(sitemaps)} sitemap files.")
                sitemap_info = {}
                progress_bar = st.progress(0)
                total_sitemaps = len(sitemaps)
                status_text = st.empty()
                
                for idx, sitemap in enumerate(sitemaps):
                    status_text.text(f"({idx + 1}/{total_sitemaps}) Now Analyzing: {sitemap}")
                    url_count, top_level_dirs, urls = analyze_sitemap(sitemap)
                    sitemap_info[sitemap] = {
                        'url_count': url_count,
                        'top_level_directories': top_level_dirs,
                        'urls': urls  # Keep list of URLs
                    }
                    progress_bar.progress((idx + 1) / total_sitemaps)
                status_text.text("Analysis Complete")

                # Construct data for DataFrame
                data = []
                for sitemap, info in sitemap_info.items():
                    row = {'Sitemap': sitemap, 'URL Count': int(info['url_count'])}  # Ensure URL Count has no decimal points
                    row.update(info['top_level_directories'])
                    data.append(row)

                # Create DataFrame
                df = pd.DataFrame(data)
                df.set_index('Sitemap', inplace=True)

                # Convert all NaN values to 0
                df.fillna(0, inplace=True)
                # Add a row at the top that sums the number of all other cells in the same column
                sum_row = df.sum(numeric_only=True)
                sum_row.name = 'TOTAL'
                df = pd.concat([sum_row.to_frame().T, df])
                df.sort_values(by='URL Count', ascending=False, inplace=True)
                # Display header
                st.header("Overview of the Sitemap Index")

                # Display DataFrame with increased width and highlighted non-zero cells
                st.dataframe(df)


                # Construct data for URL DataFrame
                url_data = []
                for sitemap, info in sitemap_info.items():
                    for url in info['urls']:
                        parsed_url = urlparse(url)
                        path_parts = parsed_url.path.split('/')
                        if parsed_url.path == "/" or parsed_url.path == "":
                            top_level_dir = "Homepage"
                        elif len(path_parts) == 2:
                            top_level_dir = "Others"
                        else:
                            top_level_dir = path_parts[1]
                        url_data.append({'Sitemap': sitemap, 'URL': url, 'Top-Level Directory': top_level_dir})

                # Create URL DataFrame
                url_df = pd.DataFrame(url_data)

                # Display header
                st.header("All URLs")

                # Display only the first 200 rows of the URL DataFrame
                st.dataframe(url_df.head(200))
                st.write(f"Note: This is just a preview. The full data set has a total of {len(url_df)} URLs. Please download to see them all.")

                # Provide a downloadable button for full URL DataFrame
                url_csv = url_df.to_csv().encode('utf-8')
                st.download_button(
                    label="Download URL data as CSV",
                    data=url_csv,
                    file_name='sitemap_urls.csv',
                    mime='text/csv',
                    on_click=lambda: st.session_state.update({"downloaded": True})
                )
            except requests.exceptions.RequestException as e:
                st.error(f"An error occurred: {e}")
                st.write("The website might have some bot detection that prevents the script from working.")
        else:
            st.error("Please enter a valid Sitemap Index URL.")
            st.write("The website might have some bot detection that prevents the script from working.")
            
elif analysis_type == "Sitemap File":
    sitemap_url = st.text_input("Enter the Sitemap URL:")
    if st.button("Run Analysis"):
        if sitemap_url:
            try:
                url_count, top_level_dirs, urls = analyze_sitemap(sitemap_url)
                st.write(f"Found {int(url_count)} URLs in the sitemap.")  # Ensure URL Count has no decimal points

                # Construct data for DataFrame
                data = [{'Top-Level Directory': dir, 'URL Count': int(count)} for dir, count in top_level_dirs.items()]  # Ensure URL Count has no decimal points

                # Create DataFrame
                df = pd.DataFrame(data)
                df.set_index('Top-Level Directory', inplace=True)

                # Sort DataFrame by URL Count in descending order
                df.sort_values(by='URL Count', ascending=False, inplace=True)

                st.header("Overview of the Sitemap File")

                # Display DataFrame
                st.dataframe(df)


                # Construct data for URL DataFrame
                url_data = []
                for url in urls:
                    parsed_url = urlparse(url)
                    path_parts = parsed_url.path.split('/')
                    if parsed_url.path == "/" or parsed_url.path == "":
                        top_level_dir = "Homepage"
                    elif len(path_parts) == 2:
                        top_level_dir = "Others"
                    else:
                        top_level_dir = path_parts[1]
                    url_data.append({'Sitemap': sitemap_url, 'URL': url, 'Top-Level Directory': top_level_dir})

                # Create URL DataFrame
                url_df = pd.DataFrame(url_data)

                st.header("All URLs")
                # Display only the first 200 rows of the URL DataFrame
                st.dataframe(url_df.head(200))
                st.write(f"Note: This is just a preview. The full data set has a total of {len(url_df)} URLs. Please download to see them all.")

                # Provide a downloadable button for full URL DataFrame
                url_csv = url_df.to_csv().encode('utf-8')
                st.download_button(
                    label="Download all URLs as CSV",
                    data=url_csv,
                    file_name='sitemap_urls.csv',
                    mime='text/csv',
                    on_click=lambda: st.session_state.update({"downloaded": True})
                )
            except requests.exceptions.RequestException as e:
                st.error(f"An error occurred: {e}")
                st.write("The website might have some bot detection that prevents the script from working.")
        else:
            st.error("Please enter a valid Sitemap URL.")
            st.write("The website might have some bot detection that prevents the script from working.")
